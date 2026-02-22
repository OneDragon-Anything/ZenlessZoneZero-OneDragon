from one_dragon.launcher.exe_launcher import ExeLauncher
from one_dragon.version import __version__


class ZLauncher(ExeLauncher):
    """绝区零启动器"""

    def __init__(self):
        ExeLauncher.__init__(self, "绝区零 一条龙 启动器", __version__)

    def run_onedragon_mode(self, launch_args: list[str]) -> None:
        from zzz_od.application.zzz_application_launcher import main
        main(launch_args)

    def run_gui_mode(self) -> None:
        import ctypes
        # 隐藏控制台窗口，避免 GUI 模式下出现黑窗口
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE

        from zzz_od.gui.app import main
        main()


if __name__ == '__main__':
    launcher = ZLauncher()
    launcher.run()
