import os
from typing import Callable, Optional, Tuple
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.base.web.common_downloader import CommonDownloaderParam
from one_dragon.base.web.zip_downloader import ZipDownloader
from one_dragon.envs.env_config import DEFAULT_ENV_PATH
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.install_card.base_install_card import BaseInstallCard


class LauncherInstallCard(BaseInstallCard):

    def __init__(self, ctx: OneDragonEnvContext):

        BaseInstallCard.__init__(
            self,
            ctx=ctx,
            title_cn='启动器',
            install_method=self.install_launcher
        )

        work_dir = os_utils.get_work_dir()
        zip_file_name = f'{ctx.project_config.project_name}-Launcher.zip'

        param = CommonDownloaderParam(
            save_file_path=DEFAULT_ENV_PATH,
            save_file_name=zip_file_name,
            github_release_download_url=f'{self.ctx.project_config.github_homepage}/releases/latest/download/{zip_file_name}',
            check_existed_list=[os.path.join(work_dir, 'OneDragon-Launcher.exe')],
            unzip_dir_path=work_dir,
        )
        self.downloader = ZipDownloader(param)

    def install_launcher(self, progress_callback: Optional[Callable[[float, str], None]]) -> Tuple[bool, str]:
        proxy_url = self.ctx.env_config.personal_proxy if self.ctx.env_config.is_personal_proxy else None
        ghproxy_url = self.ctx.env_config.gh_proxy_url if self.ctx.env_config.is_gh_proxy else None
        success = self.downloader.download(proxy_url=proxy_url, ghproxy_url=ghproxy_url, progress_callback=progress_callback)
        return (True, gt('安装启动器成功')) if success else (False, gt('安装启动器失败'))

    def check_launcher_exist(self) -> bool:
        """
        检查启动器是否存在
        :return: 是否存在
        """
        launcher_path = os.path.join(os_utils.get_work_dir(), 'OneDragon-Launcher.exe')
        return os.path.exists(launcher_path)

    def after_progress_done(self, success: bool, msg: str) -> None:
        """
        安装结束的回调，由子类自行实现
        :param success: 是否成功
        :param msg: 提示信息
        :return:
        """
        if success:
            self.check_and_update_display()
        else:
            self.update_display(FluentIcon.INFO.icon(color=FluentThemeColor.RED.value), gt(msg))

    def get_display_content(self) -> Tuple[QIcon, str]:
        """
        获取需要显示的状态，由子类自行实现
        :return: 显示的图标、文本
        """
        if self.check_launcher_exist():
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.DEFAULT_BLUE.value)
            msg = gt('已安装')
            return icon, msg
        else:
            icon = FluentIcon.INFO.icon(color=FluentThemeColor.RED.value)
            msg = gt('需下载')

        return icon, msg
