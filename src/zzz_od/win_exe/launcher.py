from one_dragon.launcher.exe_launcher import ExeLauncher
from one_dragon.version import __version__


class ZLauncher(ExeLauncher):
    """绝区零启动器"""

    def __init__(self):
        ExeLauncher.__init__(self, "绝区零 一条龙 启动器", __version__)

    def run_onedragon_mode(self, launch_args) -> None:
        import sys

        from zzz_od.application.zzz_application_launcher import ZApplicationLauncher

        sys.argv = [sys.argv[0]] + launch_args
        launcher = ZApplicationLauncher()
        launcher.run()

    def run_gui_mode(self) -> None:
        import ctypes
        import sys
        import traceback
        import webbrowser

        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QApplication
            from qfluentwidgets import Theme, setTheme

            from zzz_od.context.zzz_context import ZContext
            from zzz_od.gui.app import AppWindow

            QApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )
            app = QApplication(sys.argv)
            app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

            _ctx = ZContext()

        except Exception:
            stack_trace = traceback.format_exc()

            # 显示错误弹窗，询问用户是否打开排障文档
            error_message = f"启动一条龙失败,报错信息如下:\n{stack_trace}\n\n是否打开排障文档查看解决方案?"
            # MB_ICONERROR | MB_OKCANCEL = 0x10 | 0x01 = 0x11
            # 返回值: IDOK = 1, IDCANCEL = 2
            result = ctypes.windll.user32.MessageBoxW(0, error_message, "错误", 0x11)

            # 如果用户点击确定，则打开排障文档
            if result == 1:  # IDOK
                webbrowser.open("https://docs.qq.com/doc/p/7add96a4600d363b75d2df83bb2635a7c6a969b5")

            sys.exit(1)

        # 设置主题
        setTheme(Theme[_ctx.custom_config.theme.upper()])

        # 创建并显示主窗口
        w = AppWindow(_ctx)

        w.show()
        w.activateWindow()

        # 加载配置
        _ctx.init_async()

        # 启动应用程序事件循环
        quit_code = app.exec()

        _ctx.after_app_shutdown()

        sys.exit(quit_code)


if __name__ == '__main__':
    launcher = ZLauncher()
    launcher.run()
