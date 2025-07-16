import sys

from PySide6.QtWidgets import QApplication
from qfluentwidgets import NavigationItemPosition, Theme, setTheme

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon_qt.app.installer import InstallerWindowBase
from one_dragon_qt.view.code_interface import CodeInterface
from one_dragon_qt.view.install_interface import InstallerInterface
from one_dragon_qt.view.installer_setting_interface import InstallerSettingInterface
from one_dragon_qt.widgets.welcome_dialog import WelcomeDialog
from one_dragon.utils.i18_utils import gt
from zzz_od.gui.view.installer.extend_install_interface import ExtendInstallInterface


class ZInstallerWindow(InstallerWindowBase):

    def __init__(self, ctx: OneDragonEnvContext, win_title: str, parent=None):
        InstallerWindowBase.__init__(
            self,
            ctx=ctx,
            win_title=win_title,
            parent=parent,
            app_icon='zzz_logo.ico'
        )

        self._check_first_run()

    def create_sub_interface(self):
        self.add_sub_interface(InstallerInterface(self.ctx, parent=self))
        self.add_sub_interface(ExtendInstallInterface(self.ctx, parent=self))
        self.add_sub_interface(CodeInterface(self.ctx, parent=self), position=NavigationItemPosition.BOTTOM)
        self.add_sub_interface(InstallerSettingInterface(self.ctx, parent=self), position=NavigationItemPosition.BOTTOM)

    def _check_first_run(self):
        """首次运行时显示防倒卖弹窗"""
        if self.ctx.env_config.is_first_run:
            dialog = WelcomeDialog(self)
            if dialog.exec():
                self.ctx.env_config.is_first_run = False


if __name__ == '__main__':
    app = QApplication(sys.argv)
    _ctx = OneDragonEnvContext()
    # 异步更新免费代理
    _ctx.async_update_gh_proxy()
    setTheme(Theme['AUTO'])
    w = ZInstallerWindow(_ctx, gt(f'{_ctx.project_config.project_name}-installer', 'ui'))
    w.show()
    app.exec()

    _ctx.after_app_shutdown()
