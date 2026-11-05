import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from one_dragon.utils import http_utils
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.envs.ghproxy_service import GhProxyService

# 使用 ghproxy 代理的源
GITHUB_SOURCE_ID: str = 'github'
AUTO_FALLBACK_MIN_BYTES_PER_SECOND: float = 100 * 1024


@dataclass(frozen=True, slots=True)
class ResourceDownloadProgress:
    """资源下载的结构化进度。"""

    source_id: str = ''
    phase: str = 'waiting'
    downloaded_bytes: int = 0
    total_bytes: int = 0
    bytes_per_second: float = 0
    progress: float = 0
    message: str = ''


class CommonDownloaderParam:

    def __init__(
            self,
            save_file_path: str,
            save_file_name: str,
            download_urls: dict[str, str] | None = None,
            check_existed_list: list[str] | None = None,
            unzip_dir_path: str | None = None,
    ):
        """
        一个通用下载器 可提供多个下载源 并检查文件是否存在 如果存在则不进行下载

        Args:
            save_file_path (str): 文件保存的路径
            save_file_name (str): 文件保存的名称
            download_urls (Optional[dict[str, str]], optional): 源ID到下载地址的映射. Defaults to None.
            check_existed_list (Optional[list[str]], optional): 需要检查文件是否存在的列表 完整路径的列表. Defaults to None.
            unzip_dir_path (Optional[str], optional): 解压目录路径，如果为None则解压到save_file_path. Defaults to None.
        """
        self.save_file_path: str = save_file_path
        self.save_file_name: str = save_file_name
        self.download_urls: dict[str, str] = {} if download_urls is None else download_urls
        self.check_existed_list: list[str] = [] if check_existed_list is None else check_existed_list
        self.unzip_dir_path: str | None = unzip_dir_path


class CommonDownloader:

    def __init__(
            self,
            param: CommonDownloaderParam,
            ) -> None:
        """
        一个通用下载器 可提供多个下载源 按候选顺序尝试 并检查文件是否存在 如果存在则不进行下载

        Args:
            param (CommonDownloaderParam): 下载参数
        """
        self.param: CommonDownloaderParam = param
        self._last_gh_proxy_url: str | None = None
        """本次下载实际用上的代理线路，解压失败时用来把它排到候选后面。"""
        self._last_source_id: str | None = None
        """本次下载成功的源 ID，子类可以用它在后续步骤成功后再回调。"""

    def download(
            self,
            source_order: list[str] | None = None,
            proxy_url: str | None = None,
            ghproxy_url: str | None = None,
            gh_proxy_service: "GhProxyService | None" = None,
            exclude_proxy_urls: set[str] | None = None,
            record_proxy_success: bool = True,
            defer_source_success: bool = False,
            skip_if_existed: bool = True,
            progress_signal: dict[str, str | None] | None = None,
            progress_callback: Callable[[float, str], None] | None = None,
            status_callback: Callable[[ResourceDownloadProgress], None] | None = None,
            on_source_success: Callable[[str], None] | None = None,
            on_source_failure: Callable[[str], None] | None = None,
            fallback_on_slow: bool = False,
            ) -> bool:
        """
        按候选源顺序依次尝试下载 直到成功

        Args:
            source_order: 候选源ID顺序 None或与下载地址无交集时使用参数中的地址顺序
            proxy_url: 个人代理地址
            ghproxy_url: ghproxy 代理地址 只对 github 源生效 只在没有 gh_proxy_service 时使用
            gh_proxy_service: GitHub 代理线路服务 提供时对每条 github 源地址逐条尝试候选线路
            exclude_proxy_urls: 已经试过的线路 本次调用不再重复尝试
            record_proxy_success: 下载成功就记录线路 压缩包下载传 False 由解压成功后再记录
            defer_source_success: 暂不回调源成功 压缩包下载要等解压成功才算这个源可用
            skip_if_existed: 文件已存在时是否跳过下载
            progress_signal: 进度控制信号 signal=cancel 时取消下载
            progress_callback: 进度回调
            status_callback: 结构化进度回调
            on_source_success: 某个源下载成功后的回调 入参为源ID
            on_source_failure: 某个源下载失败后的回调 入参为源ID
            fallback_on_slow: 是否在候选源持续低速时尝试下一个源

        Returns:
            bool: 是否下载成功
        """
        self._last_gh_proxy_url = None
        if skip_if_existed and self.is_file_existed():
            return True

        candidates: list[str] = []
        if source_order is not None:
            candidates = [i for i in source_order if i in self.param.download_urls]
        if len(candidates) == 0:
            candidates = list(self.param.download_urls.keys())

        if len(candidates) == 0:
            log.error('没有可用的下载源')
            if status_callback is not None:
                status_callback(ResourceDownloadProgress(phase='failed', message='没有可用的下载源'))
            return False

        save_file_path = os.path.join(self.param.save_file_path, self.param.save_file_name)
        if gh_proxy_service is not None and GITHUB_SOURCE_ID in candidates:
            gh_proxy_service.ensure_probed()
        if gh_proxy_service is not None:
            gh_proxy_urls = gh_proxy_service.get_candidate_urls()
        elif ghproxy_url is not None and ghproxy_url.strip('/'):
            gh_proxy_urls = [ghproxy_url.rstrip('/')]
        else:
            gh_proxy_urls = []
        if exclude_proxy_urls:
            gh_proxy_urls = [url for url in gh_proxy_urls if url not in exclude_proxy_urls]

        for index, source_id in enumerate(candidates):
            base_download_url = self.param.download_urls[source_id]
            if source_id == GITHUB_SOURCE_ID and gh_proxy_service is not None and not gh_proxy_urls:
                # 启用了代理但没有可用线路了 不再退化成直连
                log.warning(f'从 {source_id} 下载 {self.param.save_file_name} 时线路都已试过')
                if on_source_failure is not None:
                    on_source_failure(source_id)
                continue
            if source_id == GITHUB_SOURCE_ID and gh_proxy_urls:
                attempt_urls = [f'{prefix}/{base_download_url}' for prefix in gh_proxy_urls]
            else:
                attempt_urls = [base_download_url]

            log.info(f'尝试从 {source_id} 下载 {self.param.save_file_name}')
            if status_callback is not None:
                status_callback(
                    ResourceDownloadProgress(
                        source_id=source_id,
                        phase='connecting',
                        message='正在连接',
                    )
                )

            source_success = False
            for attempt_index, download_url in enumerate(attempt_urls):
                is_last_attempt = index == len(candidates) - 1 and attempt_index == len(attempt_urls) - 1
                success = http_utils.download_file(
                    download_url=download_url,
                    save_file_path=save_file_path,
                    proxy=proxy_url,
                    min_bytes_per_second=(
                        AUTO_FALLBACK_MIN_BYTES_PER_SECOND
                        if fallback_on_slow and not is_last_attempt
                        else None
                    ),
                    progress_signal=progress_signal,
                    progress_callback=progress_callback,
                    status_callback=(
                        lambda progress, current_source=source_id: status_callback(
                            ResourceDownloadProgress(
                                source_id=current_source,
                                phase=progress.phase,
                                downloaded_bytes=progress.downloaded_bytes,
                                total_bytes=progress.total_bytes,
                                bytes_per_second=progress.bytes_per_second,
                                progress=progress.progress,
                                message=progress.message,
                            )
                        )
                        if status_callback is not None
                        else None
                    ),
                )

                if success:
                    if gh_proxy_service is not None and source_id == GITHUB_SOURCE_ID:
                        proxy_url = gh_proxy_service.match_proxy_url(download_url)
                        self._last_gh_proxy_url = proxy_url
                        if record_proxy_success and proxy_url is not None:
                            gh_proxy_service.remember_success(proxy_url)
                    self._last_source_id = source_id
                    source_success = True
                    break

                if progress_signal is not None and progress_signal.get('signal') == 'cancel':
                    # 用户主动取消 不再尝试其他源
                    return False
                if attempt_index < len(attempt_urls) - 1:
                    log.warning(f'从 {source_id} 的代理线路下载失败 换下一条')

            if source_success:
                if on_source_success is not None and not defer_source_success:
                    on_source_success(source_id)
                return True

            if on_source_failure is not None:
                on_source_failure(source_id)
            log.warning(f'从 {source_id} 下载失败 尝试下一个源')

        return False

    def is_file_existed(self) -> bool:
        """
        判断所需文件是否都已经存在了

        Returns:
            bool: 是否都存在
        """
        if not self.param.check_existed_list:
            return False
        all_existed: bool = True
        for file_name in self.param.check_existed_list:
            if not os.path.exists(file_name):
                all_existed = False
                break
        return all_existed
