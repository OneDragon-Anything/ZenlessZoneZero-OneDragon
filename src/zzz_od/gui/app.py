try:
    import sys
    from typing import Tuple
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtWidgets import QApplication
    from qfluentwidgets import NavigationItemPosition, setTheme, Theme
    from one_dragon_qt.view.like_interface import LikeInterface
    from one_dragon.base.operation.one_dragon_context import ContextInstanceEventEnum

    from one_dragon_qt.services.styles_manager import OdQtStyleSheet

    from one_dragon_qt.view.code_interface import CodeInterface
    from one_dragon_qt.view.context_event_signal import ContextEventSignal
    from one_dragon_qt.windows.app_window_base import AppWindowBase
    from one_dragon.utils import app_utils
    from one_dragon.utils.i18_utils import gt

    from zzz_od.context.zzz_context import ZContext
    from zzz_od.gui.view.accounts.app_accounts_interface import AccountsInterface
    from zzz_od.gui.view.battle_assistant.battle_assistant_interface import BattleAssistantInterface
    from zzz_od.gui.view.devtools.app_devtools_interface import AppDevtoolsInterface
    from zzz_od.gui.view.game_assistant.game_assistant import GameAssistantInterface
    from zzz_od.gui.view.hollow_zero.hollow_zero_interface import HollowZeroInterface
    from zzz_od.gui.view.home.home_interface import HomeInterface
    from zzz_od.gui.view.one_dragon.zzz_one_dragon_interface import ZOneDragonInterface
    from zzz_od.gui.view.setting.app_setting_interface import AppSettingInterface
    from zzz_od.gui.widgets.zzz_welcome_dialog import ZWelcomeDialog

    _init_error = None


    class CheckVersionRunner(QThread):

        get = Signal(tuple)

        def __init__(self, ctx: ZContext, parent=None):
            super().__init__(parent)
            self.ctx = ctx

        def run(self):
            launcher_version = app_utils.get_launcher_version()
            code_version = self.ctx.git_service.get_current_version()
            versions = (launcher_version, code_version)
            self.get.emit(versions)

    # 定义应用程序的主窗口类
    class AppWindow(AppWindowBase):

        def __init__(self, ctx: ZContext, parent=None):
            """初始化主窗口类，设置窗口标题和图标"""
            self.ctx: ZContext = ctx
            AppWindowBase.__init__(
                self,
                win_title="%s %s"
                % (
                    gt(ctx.project_config.project_name),
                    ctx.one_dragon_config.current_active_instance.name,
                ),
                project_config=ctx.project_config,
                app_icon="zzz_logo.ico",
                parent=parent,
            )

            self.ctx.listen_event(ContextInstanceEventEnum.instance_active.value, self._on_instance_active_event)
            self._context_event_signal: ContextEventSignal = ContextEventSignal()
            self._context_event_signal.instance_changed.connect(self._on_instance_active_signal)

            self._check_version_runner = CheckVersionRunner(self.ctx)
            self._check_version_runner.get.connect(self._update_version)
            self._check_version_runner.start()

            self._check_first_run()

        # 继承初始化函数
        def init_window(self):
            self.resize(1050, 700)

            # 初始化位置
            self.move(100, 100)

            # 设置配置ID
            self.setObjectName("PhosWindow")
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

            # DEBUG
            # print("————APP WINDOW STYLE————")
            # print(self.styleSheet())
            # print("————NAVIGATION INTERFACE STYLE————")
            # print(self.navigationInterface.styleSheet())
            # print("————STACKED WIDGET STYLE————")
            # print(self.stackedWidget.styleSheet())
            # print("————TITLE BAR STYLE————")
            # print(self.titleBar.styleSheet())

            # 开启磨砂效果
            # self.setAeroEffectEnabled(True)

        def create_sub_interface(self):
            """创建和添加各个子界面"""

            # 主页
            self.add_sub_interface(HomeInterface(self.ctx, parent=self))

            # 战斗助手
            self.add_sub_interface(BattleAssistantInterface(self.ctx, parent=self))

            # 一条龙
            self.add_sub_interface(ZOneDragonInterface(self.ctx, parent=self))

            # 空洞
            self.add_sub_interface(HollowZeroInterface(self.ctx, parent=self))

            # 游戏助手
            self.add_sub_interface(GameAssistantInterface(self.ctx, parent=self))

            # 点赞
            self.add_sub_interface(
                LikeInterface(self.ctx, parent=self),
                position=NavigationItemPosition.BOTTOM,
            )

            # 开发工具
            self.add_sub_interface(
                AppDevtoolsInterface(self.ctx, parent=self),
                position=NavigationItemPosition.BOTTOM,
            )

            # 代码同步
            self.add_sub_interface(
                CodeInterface(self.ctx, parent=self),
                position=NavigationItemPosition.BOTTOM,
            )

            # 多账号管理
            self.add_sub_interface(
                AccountsInterface(self.ctx, parent=self),
                position=NavigationItemPosition.BOTTOM,
            )

            # 设置
            self.add_sub_interface(
                AppSettingInterface(self.ctx, parent=self),
                position=NavigationItemPosition.BOTTOM,
            )

        def _on_instance_active_event(self, event) -> None:
            """
            切换实例后 更新title 这是context的事件 不能更新UI
            :return:
            """
            self._context_event_signal.instance_changed.emit()

        def _on_instance_active_signal(self) -> None:
            """
            切换实例后 更新title 这是Signal 可以更新UI
            :return:
            """
            self.setWindowTitle(
                "%s %s"
                % (
                    gt(self.ctx.project_config.project_name),
                    self.ctx.one_dragon_config.current_active_instance.name,
                )
            )

        def _update_version(self, versions: Tuple[str, str]) -> None:
            """
            更新版本显示
            @param ver:
            @return:
            """
            self.titleBar.setVersion(versions[0], versions[1])

        def _check_first_run(self):
            """首次运行时显示防倒卖弹窗"""
            if self.ctx.env_config.is_first_run:
                dialog = ZWelcomeDialog(self)
                if dialog.exec():
                    self.ctx.env_config.is_first_run = False


# 调用Windows错误弹窗
except Exception as e:
    import ctypes
    import traceback

    stack_trace = traceback.format_exc()
    _init_error = f"启动一条龙失败，报错信息如下:\n{stack_trace}"


# 初始化应用程序，并启动主窗口
if __name__ == "__main__":
    if _init_error is not None:
        ctypes.windll.user32.MessageBoxW(0, _init_error, "错误", 0x10)
        sys.exit(1)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

    _ctx = ZContext()

    # 加载配置
    _ctx.init_by_config()

    # 异步加载OCR
    _ctx.async_init_ocr()

    # 异步更新免费代理
    _ctx.async_update_gh_proxy()

    # 设置主题
    setTheme(Theme[_ctx.custom_config.theme.upper()])

    # 创建并显示主窗口
    w = AppWindow(_ctx)

    w.show()
    w.activateWindow()

    # 启动应用程序事件循环
    app.exec()

    _ctx.after_app_shutdown()
