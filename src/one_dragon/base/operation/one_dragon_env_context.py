from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from typing import Optional

from one_dragon.envs.download_service import DownloadService
from one_dragon.envs.env_config import EnvConfig
from one_dragon.envs.ghproxy_service import GhProxyService
from one_dragon.envs.git_service import GitService
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.envs.python_service import PythonService

ONE_DRAGON_CONTEXT_EXECUTOR = ThreadPoolExecutor(thread_name_prefix='one_dragon_context', max_workers=1)


class OneDragonEnvContext:

    def __init__(self):
        """
        存项目和环境信息的
        安装器可以使用这个减少引入依赖
        """
        self.installer_dir: Optional[str] = None

    #------------------- 需要懒加载的都使用 @cached_property -------------------#

    @cached_property
    def project_config(self):
        return ProjectConfig()

    @cached_property
    def env_config(self):
        return EnvConfig()

    @cached_property
    def download_service(self):
        return DownloadService(self.project_config, self.env_config)

    @cached_property
    def git_service(self):
        return GitService(self.project_config, self.env_config, self.download_service)

    @cached_property
    def python_service(self):
        return PythonService(self.project_config, self.env_config, self.download_service)

    @cached_property
    def gh_proxy_service(self):
        return GhProxyService(self.env_config)

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        @return:
        """
        ONE_DRAGON_CONTEXT_EXECUTOR.shutdown(wait=False, cancel_futures=True)
