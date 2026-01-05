import os
from collections.abc import Callable

from one_dragon.base.web.common_downloader import (
    CommonDownloader,
    CommonDownloaderParam,
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
            download_by_github: bool = True,
            download_by_gitee: bool = False,
            download_by_mirror_chan: bool = False,
            proxy_url: str | None = None,
            ghproxy_url: str | None = None,
            skip_if_existed: bool = True,
            progress_signal: dict[str, str | None] | None = None,
            progress_callback: Callable[[float, str], None] | None = None
            ) -> bool:
        for i in range(2):
            download_result = CommonDownloader.download(
                self,
                download_by_github=download_by_github,
                download_by_gitee=download_by_gitee,
                download_by_mirror_chan=download_by_mirror_chan,
                proxy_url=proxy_url,
                ghproxy_url=ghproxy_url,
                skip_if_existed=skip_if_existed if i == 0 else False,  # 第2次重试时必定重新下载
                progress_signal=progress_signal,
                progress_callback=progress_callback,
            )

            if not download_result:
                return download_result

            unzip_result = self.unzip()
            if unzip_result:
                break
            else:  # 可能压缩包下载不完整 解压不成功 重新下载
                log.warning('疑似压缩包损毁 重新下载')
                continue

        # 解压有可能失败 最后再判断一次文件是否已经存在了
        return self.is_file_existed()

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
