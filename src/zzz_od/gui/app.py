try:
    import sys

    from PySide6.QtCore import Qt, QThread, QTimer, Signal
    from PySide6.QtWidgets import QApplication
    from qfluentwidgets import NavigationItemPosition, Theme, setTheme

    from one_dragon.base.operation.one_dragon_context import ContextInstanceEventEnum
    from one_dragon.utils import app_utils
    from one_dragon.utils.i18_utils import gt
    from one_dragon_qt.services.styles_manager import OdQtStyleSheet
    from one_dragon_qt.view.context_event_signal import ContextEventSignal
    from one_dragon_qt.windows.main_app_window_base import MainAppWindowBase
    from one_dragon_qt.windows.window import PhosTitleBar
    from zzz_od.context.zzz_context import ZContext

    _init_error = None


    class CtxInitRunner(QThread):
        finished = Signal()

        def __init__(self, ctx: ZContext, window: MainAppWindowBase, parent=None):
            super().__init__(parent)
            self.ctx = ctx
            self._window = window

        def run(self):
            self.ctx.init()
            self._window.on_ctx_ready()
            self.finished.emit()


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
    class AppWindow(MainAppWindowBase):
        titleBar: PhosTitleBar

        def __init__(self, ctx: ZContext, parent=None):
            """初始化主窗口类，设置窗口标题和图标"""
            self.ctx: ZContext = ctx

            # 记录应用启动时间
            import time
            self._app_start_time = time.time()

            MainAppWindowBase.__init__(
                self,
                ctx=ctx,
                win_title="%s %s"
                % (
                    gt(ctx.project_config.project_name),
                    ctx.one_dragon_config.current_active_instance.name,
                ),
                project_config=ctx.project_config,
                app_icon="logo.ico",
                parent=parent,
            )

            self.ctx.listen_event(ContextInstanceEventEnum.instance_active.value, self._on_instance_active_event)
            self._context_event_signal: ContextEventSignal = ContextEventSignal()
            self._context_event_signal.instance_changed.connect(self._on_instance_active_signal)

            self._check_version_runner = CheckVersionRunner(self.ctx)
            self._check_version_runner.get.connect(self._update_version)

            # 延迟发送应用启动事件，等待窗口完全显示
            self._launch_timer = QTimer()
            self._launch_timer.setSingleShot(True)
            self._launch_timer.timeout.connect(self._after_app_launch)
            self._launch_timer.start(2000)  # 2秒后发送，确保UI完全渲染

        # 继承初始化函数
        def init_window(self):
            self.resize(1140, 760)  # 3:2比例

            # 初始化位置
            screen = QApplication.primaryScreen()
            geometry = screen.availableGeometry()
            w, h = geometry.width(), geometry.height()
            self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

            # 设置配置ID
            self.setObjectName("PhosWindow")
            self.navigationInterface.setObjectName("NavigationInterface")
            self.stackedWidget.setObjectName("StackedWidget")
            self.titleBar.setObjectName("TitleBar")

            # 布局样式调整
            self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
            self.navigationInterface.setContentsMargins(0, 0, 0, 0)

            # 配置样式
            OdQtStyleSheet.NAVIGATION_INTERFACE.apply(self.navigationInterface)
            OdQtStyleSheet.STACKED_WIDGET.apply(self.stackedWidget)
            OdQtStyleSheet.AREA_WIDGET.apply(self.areaWidget)
            OdQtStyleSheet.TITLE_BAR.apply(self.titleBar)

        def create_sub_interface(self):
            """创建和添加各个子界面"""
            super().create_sub_interface()

            # 主页
            from zzz_od.gui.view.home.home_interface import HomeInterface
            self.add_sub_interface(HomeInterface(self.ctx, parent=self))

            # 游戏助手
            from zzz_od.gui.view.game_assistant.game_assistant_interface import GameAssistantInterface
            self.add_sub_interface(GameAssistantInterface(self.ctx, parent=self))

            # 一条龙
            from zzz_od.gui.view.one_dragon.zzz_one_dragon_interface import ZOneDragonInterface
            self.add_sub_interface(ZOneDragonInterface(self.ctx, parent=self))

            # 应用运行
            from zzz_od.gui.view.standalone.zzz_standalone_app_interface import ZStandaloneAppInterface
            self.add_sub_interface(ZStandaloneAppInterface(self.ctx, parent=self))

            # 画中画
            from one_dragon_qt.widgets.pip_button import PipButton
            self.pip_btn = PipButton(self.ctx, parent=self)
            self.add_nav_widget(self.pip_btn)

            # 点赞
            from one_dragon_qt.view.like_interface import LikeInterface
            self.add_sub_interface(
                LikeInterface(self.ctx, parent=self),
                position=NavigationItemPosition.BOTTOM,
            )

            # 开发工具
            from zzz_od.gui.view.devtools.app_devtools_interface import AppDevtoolsInterface
            self.add_sub_interface(
                AppDevtoolsInterface(self.ctx, parent=self),
                position=NavigationItemPosition.BOTTOM,
            )

            # 代码同步
            from one_dragon_qt.view.code_interface import CodeInterface
            self.add_sub_interface(
                CodeInterface(self.ctx, parent=self),
                position=NavigationItemPosition.BOTTOM,
            )

            # 多账号管理
            from zzz_od.gui.view.accounts.app_accounts_interface import AccountsInterface
            self.add_sub_interface(
                AccountsInterface(self.ctx, parent=self),
                position=NavigationItemPosition.BOTTOM,
            )

            # 设置
            from zzz_od.gui.view.setting.app_setting_interface import AppSettingInterface
            self.add_sub_interface(
                AppSettingInterface(self.ctx, parent=self),
                position=NavigationItemPosition.BOTTOM,
            )

            # 连接导航变化信号
            self.stackedWidget.currentChanged.connect(self._on_navigation_changed)

        def _on_navigation_changed(self, index):
            """导航变化时的处理"""
            self._last_stack_idx = index

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

        def _update_version(self, versions: tuple[str, str]) -> None:
            """
            更新版本显示
            @param ver:
            @return:
            """
            self.titleBar.setLauncherVersion(versions[0])
            self.titleBar.setCodeVersion(versions[1])

        def _check_first_run(self):
            """首次运行时显示防倒卖弹窗"""
            if self.ctx.env_config.is_first_run:
                from one_dragon_qt.widgets.welcome_dialog import WelcomeDialog
                dialog = WelcomeDialog(self, gt('欢迎使用绝区零一条龙'))
                if dialog.exec():
                    self.ctx.env_config.is_first_run = False

        def _after_app_launch(self):
            """异步处理应用启动后需要处理的事情"""
            self._check_version_runner.start()
            self._check_first_run()

        def closeEvent(self, event):
            """窗口关闭事件"""
            if hasattr(self, 'pip_btn') and self.pip_btn:
                self.pip_btn.dispose()

            # 调用父类的关闭事件
            super().closeEvent(event)


except Exception:
    import ctypes
    import traceback
    import webbrowser

    stack_trace = traceback.format_exc()
    _init_error = f"启动一条龙失败，报错信息如下:\n{stack_trace}"


# 初始化应用程序，并启动主窗口
def main() -> None:
    if _init_error is not None:
        # 显示错误弹窗，询问用户是否打开排障文档
        error_message = f"启动一条龙失败,报错信息如下:\n{stack_trace}\n\n是否打开排障文档查看解决方案?"
        # MB_ICONERROR | MB_OKCANCEL = 0x10 | 0x01 = 0x11
        # 返回值: IDOK = 1, IDCANCEL = 2
        result = ctypes.windll.user32.MessageBoxW(0, error_message, "错误", 0x11)

        # 如果用户点击确定，则打开排障文档
        if result == 1:  # IDOK
            webbrowser.open("https://docs.qq.com/doc/p/7add96a4600d363b75d2df83bb2635a7c6a969b5")

        sys.exit(1)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

    _ctx = ZContext()

    # 设置主题
    setTheme(Theme[_ctx.custom_config.theme.upper()])

    # 创建并显示主窗口
    w = AppWindow(_ctx)

    w.show()
    w.activateWindow()

    # 加载配置
    init_runner = CtxInitRunner(_ctx, w)
    init_runner.start()

    # 启动应用程序事件循环
    quit_code = app.exec()

    _ctx.after_app_shutdown()

    sys.exit(quit_code)


if __name__ == "__main__":
    main()
