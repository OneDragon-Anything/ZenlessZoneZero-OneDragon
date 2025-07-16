from typing import Optional, Callable

from one_dragon.envs.env_config import EnvConfig
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils import http_utils


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
        return self.download_file_from_url(download_url, save_file_path, progress_callback=progress_callback)

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

        return http_utils.download_file(download_url, save_file_path,
                                        proxy=proxy, progress_callback=progress_callback)
