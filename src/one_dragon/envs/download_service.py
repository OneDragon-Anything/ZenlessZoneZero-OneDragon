import shutil
from collections.abc import Callable
from pathlib import Path

from one_dragon.envs.env_config import EnvConfig
from one_dragon.envs.ghproxy_service import GhProxyService
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.envs.repo_config import RepoConfig
from one_dragon.utils import file_utils, http_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class DownloadService:
    """下载服务，统一处理各种文件下载。"""

    def __init__(self, project_config: ProjectConfig, env_config: EnvConfig,
                 repo_config: RepoConfig,
                 gh_proxy_service: GhProxyService | None = None):
        """创建下载服务。

        Args:
            project_config: 项目配置。
            env_config: 环境配置。
            repo_config: 仓库配置，提供内置的 GitHub 代理候选线路。
            gh_proxy_service: 代理线路服务；不传时按配置自行创建。
        """
        self.project_config: ProjectConfig = project_config
        self.env_config: EnvConfig = env_config
        self.repo_config: RepoConfig = repo_config
        self.gh_proxy_service: GhProxyService = (
            gh_proxy_service if gh_proxy_service is not None else GhProxyService(env_config, repo_config)
        )
        self._last_gh_proxy_url: str | None = None
        """最近一次下载实际用上的代理线路，解压失败时用来把它排除。"""

    def _record_env_source_success(self, source: str) -> None:
        """记下这次真正可用的下载源，下次优先尝试；不改写用户选择的 env_source。

        Args:
            source: 本次可用的源地址。
        """
        if source != self.env_config.env_source:
            log.warning('环境下载源 %s 不可用，本次改用 %s', self.env_config.env_source, source)
        if self.env_config.last_env_source == source:
            return
        try:
            self.env_config.last_env_source = source
        except OSError:
            # 配置写不进去只影响下次优先试哪个源，不能把已经下载好的文件判成失败
            log.warning('记录上次成功的环境下载源失败，本次下载结果不受影响', exc_info=True)

    def _download_env_file_from(self, source: str, file_name: str, save_file_path: str,
                                progress_callback: Callable[[float, str], None] | None,
                                exclude_proxy_urls: set[str] | None = None,
                                attempted_proxy_urls: list[str] | None = None) -> bool:
        """从指定下载源下载一个环境文件。

        Args:
            source: 下载源地址。
            file_name: 要下载的文件名。
            save_file_path: 保存路径，包含文件名。
            progress_callback: 下载进度的回调。
            exclude_proxy_urls: 本次调用中已经试过的代理线路，不再重复尝试。
            attempted_proxy_urls: 本次实际请求过的线路，调用方用来去重和标记。

        Returns:
            是否下载成功。
        """
        download_url = f'{source}/{self.project_config.project_name}/{file_name}'
        return self.download_file_from_url(
            download_url, save_file_path, progress_callback,
            exclude_proxy_urls=exclude_proxy_urls,
            attempted_proxy_urls=attempted_proxy_urls,
        )

    def download_env_file(self, file_name: str, save_file_path: str,
                          progress_callback: Callable[[float, str], None] | None = None,
                          exclude_proxy_urls: set[str] | None = None,
                          attempted_proxy_urls: list[str] | None = None) -> bool:
        """下载环境文件。

        当前配置的源优先，下载失败后按候选顺序逐个换源，全部失败才返回失败；
        下载成功的源记到 last_env_source，下次优先尝试，不改写用户选择的 env_source。

        Args:
            file_name: 要下载的文件名。
            save_file_path: 保存路径，包含文件名。
            progress_callback: 下载进度的回调。
            exclude_proxy_urls: 本次调用中已经试过的代理线路，不再重复尝试。
            attempted_proxy_urls: 本次实际请求过的线路，调用方用来去重和标记。

        Returns:
            是否下载成功。
        """
        for source in self.env_config.get_env_source_candidates():
            if self._download_env_file_from(
                source, file_name, save_file_path, progress_callback, exclude_proxy_urls,
                attempted_proxy_urls,
            ):
                self._record_env_source_success(source)
                return True
            log.warning('从 %s 下载 %s 失败，继续尝试下一个下载源', source, file_name)
        log.error('所有环境下载源均无法下载 %s', file_name)
        return False

    def download_file_from_url(self, download_url: str, save_file_path: str,
                               progress_callback: Callable[[float, str], None] | None = None,
                               exclude_proxy_urls: set[str] | None = None,
                               attempted_proxy_urls: list[str] | None = None) -> bool:
        """从指定URL下载文件。

        GitHub 地址且启用了 ghproxy 时，按候选线路逐条尝试，每条只试一次，
        成功的线路记录为下次首选。

        Args:
            download_url: 下载URL。
            save_file_path: 保存路径，包含文件名。
            progress_callback: 下载进度的回调，进度发生改变时，通过该方法通知调用方。
            exclude_proxy_urls: 本次调用中已经试过的线路，不再重复尝试。
            attempted_proxy_urls: 本次实际请求过的线路 成功的在最后 供调用方去重和标记。

        Returns:
            是否下载成功。
        """
        if 'github.com' in download_url and self.env_config.is_gh_proxy:
            for proxy_url in self.gh_proxy_service.get_candidate_urls():
                if exclude_proxy_urls is not None and proxy_url in exclude_proxy_urls:
                    continue
                if attempted_proxy_urls is not None:
                    attempted_proxy_urls.append(proxy_url)
                if http_utils.download_file(
                    f'{proxy_url}/{download_url}',
                    save_file_path,
                    progress_callback=progress_callback,
                ):
                    self.gh_proxy_service.remember_success(proxy_url)
                    self._last_gh_proxy_url = proxy_url
                    log.info(f'GitHub 代理线路可用 {proxy_url}')
                    return True
                log.warning(f'GitHub 代理线路下载失败 换下一条 {proxy_url}')
            log.error('所有 GitHub 代理线路都下载失败')
            return False

        proxy = None
        if 'github.com' in download_url and self.env_config.is_personal_proxy:
            proxy = self.env_config.personal_proxy

        return http_utils.download_file(download_url, save_file_path, proxy=proxy, progress_callback=progress_callback)

    def download_and_extract_env_file(self, file_name: str, temp_dir: str, extract_dir: str,
                                      progress_callback: Callable[[float, str], None] | None = None,
                                      clean_temp: bool = True, retry_count: int = 2) -> bool:
        """下载并解压环境文件。

        每个候选源都要走完「下载 + 解压」，解压成功才算这个源可用：源返回的包损坏时换下一条
        代理线路，线路都试过才换下一个源；只有本次从该源下载并解压成功才记到 last_env_source。

        Args:
            file_name: 要下载的文件名。
            temp_dir: 临时下载目录。
            extract_dir: 解压目标目录。
            progress_callback: 进度回调。
            clean_temp: 是否清理临时文件，默认清理。
            retry_count: 每个源的总尝试次数（含首次），默认 2 次。

        Returns:
            是否成功。
        """
        # 确保临时目录存在
        temp_path = Path(temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)
        zip_file_path = temp_path / file_name
        extract_path = Path(extract_dir)
        # 先解压到同级临时目录 成功才替换目标目录 重装失败时现有环境不会被提前删掉
        temp_extract_path = extract_path.with_name(f'{extract_path.name}_extract_tmp')

        for source in self.env_config.get_env_source_candidates():
            # 只有 github 源才按代理线路数加尝试次数 其他源仍按 retry_count
            line_count = (
                len(self.gh_proxy_service.get_candidate_urls())
                if self.env_config.is_gh_proxy and 'github.com' in source
                else 0
            )
            max_attempts = max(retry_count, line_count + 1)
            tried_proxy_urls: set[str] = set()

            for attempt in range(max_attempts):
                # 每次尝试只标记本次下载实际用上的线路
                self._last_gh_proxy_url = None
                used_proxy_url: str | None = None
                downloaded_now: bool = False

                # 如果文件不存在，下载它
                if not zip_file_path.exists():
                    msg = f"{gt('正在下载')} {file_name}..."
                    if progress_callback is not None:
                        progress_callback(-1, msg)
                    log.info(msg)

                    attempted_proxy_urls: list[str] = []
                    success = self._download_env_file_from(
                        source, file_name, str(zip_file_path), progress_callback,
                        exclude_proxy_urls=tried_proxy_urls,
                        attempted_proxy_urls=attempted_proxy_urls,
                    )
                    # 请求过的线路（含失败的）本次调用都不再重复请求
                    tried_proxy_urls.update(attempted_proxy_urls)
                    if success and attempted_proxy_urls:
                        used_proxy_url = attempted_proxy_urls[-1]
                    self._last_gh_proxy_url = used_proxy_url
                    if not success:
                        # 这个源连下载都失败 同源再试一次仍可能碰上网络抖动
                        if attempt < max_attempts - 1:
                            log.warning(f'从 {source} 下载 {file_name} 失败 准备重试 {attempt + 1}/{max_attempts}')
                            continue
                        log.warning(f'从 {source} 下载 {file_name} 失败，尝试下一个下载源')
                        break
                    downloaded_now = True

                msg = f"{gt('正在解压')} {file_name}..."
                log.info(msg)
                if progress_callback is not None:
                    progress_callback(-1, msg)

                if temp_extract_path.exists():
                    shutil.rmtree(temp_extract_path)

                unzip_ok = file_utils.unzip_file(str(zip_file_path), str(temp_extract_path))
                if unzip_ok and not temp_extract_path.exists():
                    log.warning('解压完成但没有产生目录 %s', temp_extract_path)
                    unzip_ok = False
                if unzip_ok:
                    if extract_path.exists():
                        shutil.rmtree(extract_path)
                    try:
                        temp_extract_path.rename(extract_path)
                    except OSError:
                        log.error('替换环境目录失败 %s', extract_path, exc_info=True)
                        if temp_extract_path.exists():
                            shutil.rmtree(temp_extract_path)
                        return False

                    # 只有本次从该源下载并解压成功 才把它记为上次成功源
                    if downloaded_now:
                        self._record_env_source_success(source)
                    msg = gt('解压成功')
                    log.info(msg)
                    if progress_callback is not None:
                        progress_callback(1, msg)

                    # 成功后清理临时文件
                    if clean_temp and zip_file_path.exists():
                        zip_file_path.unlink()
                    return True

                # 解压失败，多半是这个源/线路上的包坏了：换一条没试过的线路重试
                if temp_extract_path.exists():
                    shutil.rmtree(temp_extract_path)
                msg = gt('解压失败 准备重试') if attempt < max_attempts - 1 else gt('解压失败 换下一个下载源')
                log.warning('%s（下载源 %s）', msg, source)
                if progress_callback is not None:
                    progress_callback(0, msg)

                if used_proxy_url is not None:
                    self.gh_proxy_service.mark_failed(used_proxy_url)
                    log.warning(f'代理线路下载到的内容损坏 换下一条 {used_proxy_url}')
                    self._last_gh_proxy_url = None

                # 删除损坏的文件，准备重试
                if zip_file_path.exists():
                    zip_file_path.unlink()

        # 所有候选源都试过了
        if progress_callback is not None:
            progress_callback(0, gt('下载失败 请尝试更改网络代理'))
        return False
