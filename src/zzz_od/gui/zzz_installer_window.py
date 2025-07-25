from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon_qt.app.installer import InstallerWindowBase
from one_dragon_qt.view.installer_interface import InstallerInterface
from one_dragon_qt.view.source_config_interface import SourceConfigInterface
from zzz_od.gui.view.installer.gamepad_install_card import GamepadInstallCard


class ZInstallerWindow(InstallerWindowBase):

    def __init__(self, ctx: OneDragonEnvContext, win_title: str, parent=None):
        InstallerWindowBase.__init__(
            self,
            ctx=ctx,
            win_title=win_title,
            parent=parent,
            app_icon='logo.ico'
        )

        # 隐藏左侧导航栏
        self.navigationInterface.setVisible(False)

        # 调整标题栏位置使其左对齐
        self._adjust_title_bar_position()

    def _adjust_title_bar_position(self):
        """调整标题栏位置到左边"""
        self.titleBar.move(0, 0)
        self.titleBar.resize(self.width(), self.titleBar.height())

    def resizeEvent(self, event):
        """重写窗口大小改变事件"""
        InstallerWindowBase.resizeEvent(self, event)
        self._adjust_title_bar_position()

    def create_sub_interface(self):
        # 创建镜像源配置界面
        self.source_config_interface = SourceConfigInterface(self.ctx, parent=self)
        self.source_config_interface.finished.connect(self._on_source_config_finished)
        self.add_sub_interface(self.source_config_interface)

        # 创建主安装界面
        extend_install_cards = [GamepadInstallCard(self.ctx)]
        self.main_installer_interface = InstallerInterface(self.ctx, parent=self,
                                                           extra_install_cards=extend_install_cards)
        self.add_sub_interface(self.main_installer_interface)

        # 初始显示镜像源配置界面
        self.stackedWidget.setCurrentWidget(self.source_config_interface)

    def _on_source_config_finished(self, success: bool):
        """镜像源配置完成后切换到主安装界面"""
        if success:
            self.stackedWidget.setCurrentWidget(self.main_installer_interface)
