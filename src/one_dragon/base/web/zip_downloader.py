import os
from collections.abc import Callable
from pathlib import Path

from one_dragon.base.web.common_downloader import (
    CommonDownloader,
    CommonDownloaderParam,
    ResourceDownloadProgress,
)
from one_dragon.utils import file_utils
from one_dragon.utils.log_utils import log


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
            skip_if_existed: bool = True,
            progress_signal: dict[str, str | None] | None = None,
            progress_callback: Callable[[float, str], None] | None = None,
            status_callback: Callable[[ResourceDownloadProgress], None] | None = None,
            on_source_success: Callable[[str], None] | None = None,
            on_source_failure: Callable[[str], None] | None = None,
            fallback_on_slow: bool = False,
            ) -> bool:
        for i in range(2):
            download_result = CommonDownloader.download(
                self,
                source_order=source_order,
                proxy_url=proxy_url,
                ghproxy_url=ghproxy_url,
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
                break
            else:  # 可能压缩包下载不完整 解压不成功 重新下载
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
        file_utils.unzip_file(zip_file_path=zip_file_path, unzip_dir_path=unzip_dir)
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
