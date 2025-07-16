import os
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from qfluentwidgets import NavigationItemPosition, SplashScreen
from typing import Optional

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon_qt.windows.app_window_base import AppWindowBase
from one_dragon.utils import os_utils
from one_dragon_qt.services.styles_manager import OdQtStyleSheet


class InstallerWindowBase(AppWindowBase):
    """ Main Interface """

    def __init__(self, ctx: OneDragonEnvContext,
                 win_title: str,
                 app_icon: Optional[str] = None, parent=None):
        self.ctx: OneDragonEnvContext = ctx
        AppWindowBase.__init__(self, win_title=win_title,
                               project_config=ctx.project_config, app_icon=app_icon,
                               parent=parent)
        self._last_stack_idx: int = 0

        # 设置窗口标题
        self.setWindowTitle(win_title)
        if app_icon is not None:
            app_icon_path = os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), app_icon)
            self.setWindowIcon(QIcon(app_icon_path))

        # 初始化窗口
        self.init_window()

        # 创建启动页面
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(144, 144))

        # 在创建其他子页面前先显示主界面
        self.show()

        self.stackedWidget.currentChanged.connect(self.init_interface_on_shown)
        self.create_sub_interface()

        # 隐藏启动页面
        self.splashScreen.finish()

    def create_sub_interface(self) -> None:
        """
        创建子页面
        :return:
        """
        pass

    def add_sub_interface(self, interface: BaseInterface, position=NavigationItemPosition.TOP):
        self.addSubInterface(interface, interface.nav_icon, interface.nav_text, position=position)

    def init_interface_on_shown(self, index: int) -> None:
        """
        切换子界面时 初始化子界面的显示
        :return:
        """
        if index != self._last_stack_idx:
            last_interface: BaseInterface = self.stackedWidget.widget(self._last_stack_idx)
            if isinstance(last_interface, BaseInterface):
                last_interface.on_interface_hidden()
            self._last_stack_idx = index

        base_interface: BaseInterface = self.stackedWidget.currentWidget()
        if isinstance(base_interface, BaseInterface):
            base_interface.on_interface_shown()

    # 继承初始化函数
    def init_window(self):
        self.resize(960, 640)

        # 初始化位置
        self.move(100, 100)

        # 设置配置ID
        self.setObjectName("PhosWindow")
        self.navigationInterface.setObjectName("NavigationInterface")
        self.stackedWidget.setObjectName("StackedWidget")
        self.titleBar.setObjectName("TitleBar")    

        # 布局样式调整
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.stackedWidget.setContentsMargins(0, 28, 0, 0)
        self.navigationInterface.setContentsMargins(0, 28, 0, 0)

        # 配置样式
        OdQtStyleSheet.APP_WINDOW.apply(self)
        OdQtStyleSheet.NAVIGATION_INTERFACE.apply(self.navigationInterface)
        OdQtStyleSheet.STACKED_WIDGET.apply(self.stackedWidget)
        OdQtStyleSheet.TITLE_BAR.apply(self.titleBar)

        # 设置参数
        self.titleBar.issue_url = f"{self.ctx.project_config.github_homepage}/issues"