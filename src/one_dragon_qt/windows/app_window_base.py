import os

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from qfluentwidgets import NavigationItemPosition, SplashScreen

from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils import os_utils
from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon_qt.widgets.navigation_button import NavigationButton
from one_dragon_qt.windows.window import PhosWindow


class AppWindowBase(PhosWindow):

    def __init__(self,
                 win_title: str,
                 project_config: ProjectConfig,
                 app_icon: str | None = None,
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

        # 初始化窗口
        self.init_window()

        # 在创建其他子页面前先显示主界面
        self.show()

        self.stackedWidget.beforeCurrentChanged.connect(self._on_before_interface_changed)
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
        """添加子页面，并在导航栏创建对应按钮"""
        self.addSubInterface(interface, interface.nav_icon, interface.nav_text, position=position)

    def add_nav_widget(self, widget: NavigationButton,
                       position: NavigationItemPosition = NavigationItemPosition.TOP) -> None:
        """在导航栏末尾添加自定义按钮"""
        self.insert_nav_widget(-1, widget, position)

    def insert_nav_widget(self, index: int, widget: NavigationButton,
                          position: NavigationItemPosition = NavigationItemPosition.TOP) -> None:
        """在导航栏指定位置插入自定义按钮"""
        self.navigationInterface.insertWidget(
            index, widget.objectName(), widget, widget.on_click, position,
        )

    def init_window(self):
        self.resize(960, 820)
        self.move(100, 100)

    def _on_before_interface_changed(self, old_idx: int, new_idx: int) -> None:
        """切换前通知旧页面，确保视觉状态在切换之前恢复。"""
        old_widget = self.stackedWidget.widget(old_idx)
        if isinstance(old_widget, BaseInterface):
            old_widget.on_interface_leave()

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
