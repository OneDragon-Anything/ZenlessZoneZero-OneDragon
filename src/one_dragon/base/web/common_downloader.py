import os
from typing import Callable, Optional

from one_dragon.utils import http_utils
from one_dragon.utils.log_utils import log


class CommonDownloaderParam:

    def __init__(
            self,
            save_file_path: str,
            save_file_name: str,
            github_release_download_url: Optional[str] = None,
            gitee_release_download_url: Optional[str] = None,
            mirror_chan_download_url: Optional[str] = None,
            check_existed_list: Optional[list[str]] = None,
    ):
        """
        一个通用下载器 可提供3个下载源 并检查文件是否存在 如果存在则不进行下载

        Args:
            save_file_path (str): 文件保存的路径
            save_file_name (str): 文件保存的名称
            github_release_download_url (Optional[str], optional): Github Release下载地址. Defaults to None.
            gitee_release_download_url (Optional[str], optional): Gitee Release下载地址. Defaults to None.
            mirror_chan_download_url (Optional[str], optional): Mirror酱下载地址. Defaults to None.
            check_existed_list (Optional[list[str]], optional): 需要检查文件是否存在的列表 完整路径的列表. Defaults to None.
        """
        self.save_file_path: str = save_file_path
        self.save_file_name: str = save_file_name
        self.github_release_download_url: Optional[str] = github_release_download_url
        self.gitee_release_download_url: Optional[str] = gitee_release_download_url
        self.mirror_chan_download_url: Optional[str] = mirror_chan_download_url
        self.check_existed_list: list[str] = [] if check_existed_list is None else check_existed_list


class CommonDownloader:

    def __init__(
            self,
            param: CommonDownloaderParam,
            ) -> None:
        """
        一个通用下载器 可提供3个下载源 并检查文件是否存在 如果存在则不进行下载

        Args:
            param (CommonDownloaderParam): 下载参数
        """
        self.param: CommonDownloaderParam = param

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
        if skip_if_existed and self.is_file_existed():
            return True

        download_url: str = ''
        if download_by_github and self.param.github_release_download_url is not None:
            if ghproxy_url is not None:
                download_url=f'{ghproxy_url}/{self.param.github_release_download_url}'
            else:
                download_url = self.param.github_release_download_url
        elif download_by_gitee and self.param.gitee_release_download_url is not None:
            download_url = self.param.gitee_release_download_url
        elif download_by_mirror_chan and self.param.mirror_chan_download_url is not None:
            download_url = self.param.mirror_chan_download_url

        if download_url == '':
            log.error('没有指定下载方法或对应的下载地址')
            return False

        return http_utils.download_file(
            download_url=download_url,
            save_file_path=os.path.join(self.param.save_file_path, self.param.save_file_name),
            proxy=proxy_url,
            progress_callback=progress_callback)

    def is_file_existed(self) -> bool:
        """
        判断所需文件是否都已经存在了

        Returns:
            bool: 是否都存在
        """
        all_existed: bool = True
        for file_name in self.param.check_existed_list:
            if not os.path.exists(file_name):
                all_existed = False
                break
        return all_existed
