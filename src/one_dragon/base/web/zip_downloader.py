import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from one_dragon.base.web.common_downloader import (
    GITHUB_SOURCE_ID,
    CommonDownloader,
    CommonDownloaderParam,
    ResourceDownloadProgress,
)
from one_dragon.utils import file_utils
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.envs.ghproxy_service import GhProxyService


class ZipDownloader(CommonDownloader):

    def __init__(
            self,
            param: CommonDownloaderParam,
            ) -> None:
        """
        一个Zip的通用下载器 可提供3个下载源 并检查文件是否存在 如果存在则不进行下载 下载后进行文件解压

        Args:
            param (CommonDownloaderParam): 下载参数
        """
        CommonDownloader.__init__(
            self,
            param=param,
        )

    def download(
            self,
            source_order: list[str] | None = None,
            proxy_url: str | None = None,
            ghproxy_url: str | None = None,
            gh_proxy_service: "GhProxyService | None" = None,
            exclude_proxy_urls: set[str] | None = None,
            skip_if_existed: bool = True,
            progress_signal: dict[str, str | None] | None = None,
            progress_callback: Callable[[float, str], None] | None = None,
            status_callback: Callable[[ResourceDownloadProgress], None] | None = None,
            on_source_success: Callable[[str], None] | None = None,
            on_source_failure: Callable[[str], None] | None = None,
            fallback_on_slow: bool = False,
            ) -> bool:
        tried_proxy_urls: set[str] = set(exclude_proxy_urls or ())
        failed_sources: set[str] = set()
        # 每次解压失败换一条没试过的线路 试完为止 不只重试固定两次
        max_rounds = 2
        if gh_proxy_service is not None:
            max_rounds = max(2, len(gh_proxy_service.get_candidate_urls()) + 1)

        for i in range(max_rounds):
            download_result = CommonDownloader.download(
                self,
                source_order=source_order,
                proxy_url=proxy_url,
                ghproxy_url=ghproxy_url,
                gh_proxy_service=gh_proxy_service,
                exclude_proxy_urls=tried_proxy_urls,
                exclude_source_ids=failed_sources,
                record_proxy_success=False,
                defer_source_success=True,
                skip_if_existed=skip_if_existed if i == 0 else False,  # 第2次重试时必定重新下载
                progress_signal=progress_signal,
                progress_callback=progress_callback,
                status_callback=status_callback,
                on_source_success=on_source_success,
                on_source_failure=on_source_failure,
                fallback_on_slow=fallback_on_slow,
            )

            if not download_result:
                return download_result

            if status_callback is not None:
                status_callback(ResourceDownloadProgress(phase='extracting', progress=1, message='正在解压'))
            unzip_result = self.unzip()
            if unzip_result:
                # 压缩包校验过了才把这条线路记成可用 避免坏包把线路记成首选
                if gh_proxy_service is not None and self._last_gh_proxy_url is not None:
                    gh_proxy_service.remember_success(self._last_gh_proxy_url)
                # 解压成功才算这个源可用 回调源成功
                if on_source_success is not None and self._last_source_id is not None:
                    on_source_success(self._last_source_id)
                break
            else:  # 可能压缩包下载不完整 解压不成功 重新下载
                # 这条线路返回的压缩包是坏的 这次调用里不再试它
                if gh_proxy_service is not None and self._last_gh_proxy_url is not None:
                    tried_proxy_urls.add(self._last_gh_proxy_url)
                    gh_proxy_service.mark_failed(self._last_gh_proxy_url)
                    log.warning(f'代理线路下载到的压缩包损坏 换下一条 {self._last_gh_proxy_url}')
                    self._last_gh_proxy_url = None
                # 这个源给的包是坏的 自动模式下先清掉上次成功记录
                if self._last_source_id is not None:
                    # github 还剩没试过的线路时 只换线路不排除整个源
                    has_line_left = (
                        self._last_source_id == GITHUB_SOURCE_ID
                        and gh_proxy_service is not None
                        and any(
                            url not in tried_proxy_urls
                            for url in gh_proxy_service.get_candidate_urls()
                        )
                    )
                    if not has_line_left:
                        failed_sources.add(self._last_source_id)
                    if on_source_failure is not None:
                        on_source_failure(self._last_source_id)
                log.warning('疑似压缩包损毁 重新下载')
                continue

        # 解压有可能失败 最后再判断一次解压产物是否已经存在
        success = CommonDownloader.is_file_existed(self)
        if not success:
            archive = Path(self.param.save_file_path) / self.param.save_file_name
            archive.unlink(missing_ok=True)
        return success

    def unzip(self) -> bool:
        """
        对目标压缩包进行解压
        """
        # 文件已存在则不解压
        exists = CommonDownloader.is_file_existed(self)
        if exists:
            return True

        zip_file_path = os.path.join(self.param.save_file_path, self.param.save_file_name)
        if not os.path.exists(zip_file_path):
            return False

        # 使用指定的解压路径，如果没有指定则使用save_file_path
        unzip_dir = self.param.unzip_dir_path or self.param.save_file_path
        os.makedirs(unzip_dir, exist_ok=True)
        # 记录解压前还缺哪些目标文件 解压失败时清掉只写了一半的产物
        missing_before = [f for f in self.param.check_existed_list if not os.path.exists(f)]
        unzip_ok = file_utils.unzip_file(zip_file_path=zip_file_path, unzip_dir_path=unzip_dir)
        if not unzip_ok:
            log.warning(f'解压失败 {zip_file_path}')
            for missing_file in missing_before:
                if os.path.exists(missing_file):
                    try:
                        os.remove(missing_file)
                    except OSError:
                        log.warning(f'清理未解压完的文件失败 {missing_file}')
            return False
        log.info(f"解压完成 {zip_file_path} 到 {unzip_dir}")

        # 最后判断压缩包以外的文件是否完整了 完整了才说明解压成功
        return CommonDownloader.is_file_existed(self)

    def is_file_existed(self) -> bool:
        """
        检查文件是否存在
        额外判断压缩包是否已经存在了
        """
        exists = CommonDownloader.is_file_existed(self)
        if exists:
            return True

        zip_file_path = os.path.join(self.param.save_file_path, self.param.save_file_name)
        return os.path.exists(zip_file_path)
