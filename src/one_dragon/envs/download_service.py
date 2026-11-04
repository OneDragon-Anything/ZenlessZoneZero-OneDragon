import shutil
from collections.abc import Callable
from pathlib import Path

from one_dragon.envs.env_config import EnvConfig
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils import file_utils, http_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class DownloadService:
    """下载服务，统一处理各种文件下载"""

    def __init__(self, project_config: ProjectConfig, env_config: EnvConfig):
        self.project_config: ProjectConfig = project_config
        self.env_config: EnvConfig = env_config

    def _record_env_source_success(self, source: str) -> None:
        """记下这次真正可用的下载源，下次优先尝试；不改写用户选择的 env_source。

        Args:
            source: 本次可用的源地址。
        """
        if source != self.env_config.env_source:
            log.warning('环境下载源 %s 不可用，本次改用 %s', self.env_config.env_source, source)
        if self.env_config.last_env_source != source:
            self.env_config.last_env_source = source

    def _download_env_file_from(self, source: str, file_name: str, save_file_path: str,
                                progress_callback: Callable[[float, str], None] | None) -> bool:
        """从指定下载源下载一个环境文件。

        Args:
            source: 下载源地址。
            file_name: 要下载的文件名。
            save_file_path: 保存路径，包含文件名。
            progress_callback: 下载进度的回调。

        Returns:
            是否下载成功。
        """
        download_url = f'{source}/{self.project_config.project_name}/{file_name}'
        return self.download_file_from_url(download_url, save_file_path, progress_callback)

    def download_env_file(self, file_name: str, save_file_path: str,
                          progress_callback: Callable[[float, str], None] | None = None) -> bool:
        """下载环境文件。

        当前配置的源优先，下载失败后按候选顺序逐个换源，全部失败才返回失败；
        下载成功的源记到 last_env_source，下次优先尝试，不改写用户选择的 env_source。

        Args:
            file_name: 要下载的文件名。
            save_file_path: 保存路径，包含文件名。
            progress_callback: 下载进度的回调。

        Returns:
            是否下载成功。
        """
        for source in self.env_config.get_env_source_candidates():
            if self._download_env_file_from(source, file_name, save_file_path, progress_callback):
                self._record_env_source_success(source)
                return True
            log.warning('从 %s 下载 %s 失败，继续尝试下一个下载源', source, file_name)
        log.error('所有环境下载源均无法下载 %s', file_name)
        return False

    def download_file_from_url(self, download_url: str, save_file_path: str,
                               progress_callback: Callable[[float, str], None] | None = None) -> bool:
        """
        从指定URL下载文件
        :param download_url: 下载URL
        :param save_file_path: 保存路径，包含文件名
        :param progress_callback: 下载进度的回调，进度发生改变时，通过该方法通知调用方。
        :return: 是否下载成功
        """
        proxy = None
        if 'github.com' in download_url:
            if self.env_config.is_gh_proxy:
                download_url = f'{self.env_config.gh_proxy_url}/{download_url}'
            elif self.env_config.is_personal_proxy:
                proxy = self.env_config.personal_proxy

        return http_utils.download_file(download_url, save_file_path, proxy=proxy, progress_callback=progress_callback)

    def download_and_extract_env_file(self, file_name: str, temp_dir: str, extract_dir: str,
                                      progress_callback: Callable[[float, str], None] | None = None,
                                      clean_temp: bool = True, retry_count: int = 2) -> bool:
        """下载并解压环境文件。

        每个候选源都要走完「下载 + 解压」，解压成功才算这个源可用：源返回的包损坏时换下一个源，
        不会反复下载同一个坏包；只有解压成功才把源记到 last_env_source。

        Args:
            file_name: 要下载的文件名。
            temp_dir: 临时下载目录。
            extract_dir: 解压目标目录。
            progress_callback: 进度回调。
            clean_temp: 是否清理临时文件，默认清理。
            retry_count: 同一个源上解压失败后的重试次数，默认 2 次。

        Returns:
            是否成功。
        """
        temp_path = Path(temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)
        zip_file_path = temp_path / file_name
        extract_path = Path(extract_dir)

        for source in self.env_config.get_env_source_candidates():
            for attempt in range(retry_count):
                msg = f"{gt('正在下载')} {file_name}..."
                if progress_callback is not None:
                    progress_callback(-1, msg)
                log.info(msg)

                if not self._download_env_file_from(source, file_name, str(zip_file_path), progress_callback):
                    # 这个源连下载都失败，同源重试没意义，直接换下一个源
                    log.warning('从 %s 下载 %s 失败，尝试下一个下载源', source, file_name)
                    if zip_file_path.exists():
                        zip_file_path.unlink()
                    break

                msg = f"{gt('正在解压')} {file_name}..."
                log.info(msg)
                if progress_callback is not None:
                    progress_callback(-1, msg)

                # 如果目标目录存在，先清理
                if extract_path.exists():
                    shutil.rmtree(extract_path)

                if file_utils.unzip_file(str(zip_file_path), str(extract_path)):
                    self._record_env_source_success(source)
                    msg = gt('解压成功')
                    log.info(msg)
                    if progress_callback is not None:
                        progress_callback(1, msg)

                    # 成功后清理临时文件
                    if clean_temp and zip_file_path.exists():
                        zip_file_path.unlink()
                    return True

                # 解压失败，多半是这个源上的包坏了：删掉重试，同源重试用完就换源
                msg = gt('解压失败 准备重试') if attempt < retry_count - 1 else gt('解压失败 换下一个下载源')
                log.warning('%s（下载源 %s）', msg, source)
                if progress_callback is not None:
                    progress_callback(0, msg)

                # 删除损坏的文件，准备重试
                if zip_file_path.exists():
                    zip_file_path.unlink()

        log.error('所有环境下载源均无法下载并解压 %s', file_name)
        return False
