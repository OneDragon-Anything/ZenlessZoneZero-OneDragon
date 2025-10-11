import os
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from qfluentwidgets import NavigationItemPosition, SplashScreen
from typing import Optional

from one_dragon_qt.windows.window import PhosWindow

from one_dragon.envs.project_config import ProjectConfig
from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon.utils import os_utils


class AppWindowBase(PhosWindow):

    def __init__(self,
                 win_title: str,
                 project_config: ProjectConfig,
                 app_icon: Optional[str] = None,
                 parent=None):
        PhosWindow.__init__(self, parent=parent)
        self.project_config: ProjectConfig = project_config
        self._last_stack_idx: int = 0

        # 设置窗口标题
        self.setWindowTitle(win_title)
        if app_icon is not None:
            app_icon_path = os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), app_icon)
            self.setWindowIcon(QIcon(app_icon_path))

        # 创建启动页面
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(144, 144))

        # 在创建其他子页面前先显示主界面
        self.show()

        # 初始化窗口
        self.init_window()

        self.stackedWidget.currentChanged.connect(self.init_interface_on_shown)
        self.create_sub_interface()

        # 隐藏启动页面
        self.splashScreen.finish()

        self.titleBar.issue_url = f"{project_config.github_homepage}/issues"

    def create_sub_interface(self) -> None:
        """
        创建子页面
        :return:
        """
        pass

    def add_sub_interface(self, interface: BaseInterface, position=NavigationItemPosition.TOP):
        self.addSubInterface(interface, interface.nav_icon, interface.nav_text, position=position)

    def init_window(self):
        self.resize(960, 820)
        self.move(100, 100)

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
