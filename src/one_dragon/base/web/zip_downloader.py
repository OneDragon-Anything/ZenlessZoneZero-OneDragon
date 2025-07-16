import os
from typing import Callable, Optional

from one_dragon.utils import file_utils, http_utils
from one_dragon.utils.log_utils import log
from one_dragon.base.web.common_downloader import CommonDownloader, CommonDownloaderParam


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
            proxy_url: Optional[str] = None,
            ghproxy_url: Optional[str] = None,
            skip_if_existed: bool = True,
            progress_callback: Optional[Callable[[float, str], None]] = None
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

        file_utils.unzip_file(zip_file_path=zip_file_path, unzip_dir_path=self.param.save_file_path)
        log.info(f"解压完成 {zip_file_path}")

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
        if os.path.exists(zip_file_path):
            return True

        return False
