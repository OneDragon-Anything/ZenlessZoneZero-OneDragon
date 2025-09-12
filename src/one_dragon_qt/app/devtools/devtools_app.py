import sys
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import NavigationItemPosition, setTheme, Theme

from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.windows.app_window_base import AppWindowBase
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.i18_utils import gt

from one_dragon_qt.app.devtools.image_processing_interface import ImageProcessingInterface


class DevtoolsAppWindow(AppWindowBase):
    """开发工具主窗口"""

    def __init__(self, ctx: OneDragonContext, parent=None):
        """初始化开发工具主窗口"""
        self.ctx: OneDragonContext = ctx
        AppWindowBase.__init__(
            self,
            win_title=gt("开发工具"),
            project_config=ctx.project_config,
            app_icon="logo.ico",
            parent=parent,
        )

    def init_window(self):
        """初始化窗口"""
        self.resize(1200, 800)

        # 初始化位置
        screen = QApplication.primaryScreen()
        geometry = screen.availableGeometry()
        w, h = geometry.width(), geometry.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        # 设置配置ID
        self.setObjectName("DevtoolsWindow")
        self.navigationInterface.setObjectName("NavigationInterface")
        self.stackedWidget.setObjectName("StackedWidget")
        self.titleBar.setObjectName("TitleBar")

        # 布局样式调整
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.areaLayout.setContentsMargins(0, 32, 0, 0)
        self.navigationInterface.setContentsMargins(0, 0, 0, 0)

        # 配置样式
        OdQtStyleSheet.APP_WINDOW.apply(self)
        OdQtStyleSheet.NAVIGATION_INTERFACE.apply(self.navigationInterface)
        OdQtStyleSheet.STACKED_WIDGET.apply(self.stackedWidget)
        OdQtStyleSheet.AREA_WIDGET.apply(self.areaWidget)
        OdQtStyleSheet.TITLE_BAR.apply(self.titleBar)

    def create_sub_interface(self):
        """创建和添加各个子界面"""

        # 图像处理
        self.add_sub_interface(ImageProcessingInterface(self.ctx, parent=self))


def create_devtools_app(ctx: Optional[OneDragonContext] = None):
    """创建开发工具应用程序"""
    if ctx is None:
        # 如果没有提供上下文，创建一个基础的上下文
        from one_dragon.base.operation.one_dragon_context import OneDragonContext
        ctx = OneDragonContext()
        ctx.init_by_config()

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

    # 设置主题
    if hasattr(ctx, 'custom_config') and hasattr(ctx.custom_config, 'theme'):
        setTheme(Theme[ctx.custom_config.theme.upper()])
    else:
        setTheme(Theme.AUTO)

    # 创建并显示主窗口
    window = DevtoolsAppWindow(ctx)
    window.show()
    window.activateWindow()

    return app, window


if __name__ == "__main__":
    app, window = create_devtools_app()

    # 启动应用程序事件循环
    sys.exit(app.exec())