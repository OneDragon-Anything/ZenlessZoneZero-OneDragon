import shutil
from pathlib import Path
from typing import Optional, Callable

from one_dragon.envs.env_config import EnvConfig
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils import http_utils, file_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class DownloadService:
    """下载服务，统一处理各种文件下载"""

    def __init__(self, project_config: ProjectConfig, env_config: EnvConfig):
        self.project_config: ProjectConfig = project_config
        self.env_config: EnvConfig = env_config

    def download_env_file(self, file_name: str, save_file_path: str,
                          progress_callback: Optional[Callable[[float, str], None]] = None) -> bool:
        """
        下载环境文件
        :param file_name: 要下载的文件名
        :param save_file_path: 保存路径，包含文件名
        :param progress_callback: 下载进度的回调，进度发生改变时，通过该方法通知调用方。
        :return: 是否下载成功
        """
        download_url = f'{self.env_config.env_source}/{self.project_config.project_name}/{file_name}'
        return self.download_file_from_url(download_url, save_file_path, progress_callback)

    def download_file_from_url(self, download_url: str, save_file_path: str,
                               progress_callback: Optional[Callable[[float, str], None]] = None) -> bool:
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

        return http_utils.download_file(download_url, save_file_path, proxy, progress_callback)

    def download_and_extract_env_file(self, file_name: str, temp_dir: str, extract_dir: str,
                                      progress_callback: Optional[Callable[[float, str], None]] = None,
                                      clean_temp: bool = True, retry_count: int = 2) -> bool:
        """
        下载并解压环境文件的通用方法
        :param file_name: 要下载的文件名
        :param temp_dir: 临时下载目录
        :param extract_dir: 解压目标目录
        :param progress_callback: 进度回调
        :param clean_temp: 是否清理临时文件，默认True
        :param retry_count: 重试次数，默认2次
        :return: 是否成功
        """
        # 确保临时目录存在
        temp_path = Path(temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)

        for attempt in range(retry_count):
            zip_file_path = temp_path / file_name

            # 如果文件不存在，下载它
            if not zip_file_path.exists():
                msg = f"{gt('正在下载')} {file_name}..."
                if progress_callback is not None:
                    progress_callback(-1, msg)
                log.info(msg)

                success = self.download_env_file(file_name, str(zip_file_path), progress_callback)
                if not success:
                    msg = gt('下载失败 请尝试更改网络代理')
                    log.error(msg)
                    return False

            msg = f"{gt('正在解压')} {file_name}..."
            log.info(msg)
            if progress_callback is not None:
                progress_callback(-1, msg)

            # 如果目标目录存在，先清理
            extract_path = Path(extract_dir)
            if extract_path.exists():
                shutil.rmtree(extract_path)

            # 解压文件
            success = file_utils.unzip_file(str(zip_file_path), str(extract_path))

            if success:
                msg = gt('解压成功')
                log.info(msg)
                if progress_callback is not None:
                    progress_callback(1, msg)

                # 成功后清理临时文件
                if clean_temp and zip_file_path.exists():
                    zip_file_path.unlink()
                return True
            else:
                # 解压失败，可能是zip包损坏
                msg = gt('解压失败 准备重试') if attempt < retry_count - 1 else gt('解压失败')
                log.warning(msg)
                if progress_callback is not None:
                    progress_callback(0, msg)

                # 删除损坏的文件，准备重试
                if zip_file_path.exists():
                    zip_file_path.unlink()

        # 所有重试都失败了
        return False
