from collections.abc import Callable

from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentThemeColor

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.base.web.zip_downloader import ZipDownloader
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.install_card.base_install_card import BaseInstallCard


class LauncherInstallCard(BaseInstallCard):

    def __init__(self, ctx: OneDragonEnvContext) -> None:

        BaseInstallCard.__init__(
            self,
            ctx=ctx,
            title_cn='启动器',
            install_method=self.install_launcher
        )

        self.downloader = ZipDownloader(
            ctx.update_service.get_launcher_download_param('launcher')
        )

    def install_launcher(self, progress_callback: Callable[[float, str], None] | None) -> tuple[bool, str]:
        env_config = self.ctx.env_config
        proxy_url = env_config.personal_proxy if env_config.is_personal_proxy else None
        ghproxy_url = env_config.gh_proxy_url if env_config.is_gh_proxy else None
        success = self.downloader.download(
            source_order=env_config.get_resource_source_order(),
            proxy_url=proxy_url,
            ghproxy_url=ghproxy_url,
            progress_callback=progress_callback,
            on_source_success=env_config.mark_resource_source_success,
            on_source_failure=env_config.mark_resource_source_failure,
            fallback_on_slow=env_config.is_resource_source_auto,
        )
        return (True, gt('安装启动器成功')) if success else (False, gt('安装启动器失败'))

    def check_launcher_exist(self) -> bool:
        """
        检查启动器是否存在
        :return: 是否存在
        """
        return self.ctx.update_service.is_launcher_installed('launcher')

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

    def get_display_content(self) -> tuple[QIcon, str]:
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
