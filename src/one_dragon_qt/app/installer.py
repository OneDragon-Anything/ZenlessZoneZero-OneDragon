from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.version import __version__
from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.windows.app_window_base import AppWindowBase


class InstallerWindowBase(AppWindowBase):
    """ Main Interface """

    def __init__(self, ctx: OneDragonEnvContext,
                 win_title: str,
                 app_icon: str | None = None, parent=None):
        self.ctx: OneDragonEnvContext = ctx
        AppWindowBase.__init__(self, win_title=win_title,
                               project_config=ctx.project_config, app_icon=app_icon,
                               parent=parent)

    # 继承初始化函数
    def init_window(self):
        self.resize(960, 640)
        self.setMinimumSize(960, 640)

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
        OdQtStyleSheet.NAVIGATION_INTERFACE.apply(self.navigationInterface)
        OdQtStyleSheet.STACKED_WIDGET.apply(self.stackedWidget)
        OdQtStyleSheet.TITLE_BAR.apply(self.titleBar)

        # 设置参数
        self.titleBar.setInstallerVersion(__version__)
        self.titleBar.issue_url = f"{self.ctx.project_config.github_homepage}/issues"
