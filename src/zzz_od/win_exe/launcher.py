import contextlib

from one_dragon.devtools import python_launcher
from one_dragon.launcher.exe_launcher import ExeLauncher
from one_dragon.version import __version__


class ZLauncher(ExeLauncher):
    """绝区零启动器"""

    def __init__(self):
        ExeLauncher.__init__(self, "绝区零 一条龙 启动器", __version__)

    def run_onedragon_mode(self, launch_args) -> None:
        with contextlib.suppress(Exception):
            from one_dragon.launcher import gui_splash

            # 控制台窗口即将顶上：立即收掉 PyInstaller --splash 启动图，避免残留
            gui_splash.close_bootloader_splash()
        python_launcher.run_python(["zzz_od", "application", "zzz_application_launcher"], no_windows=False, args=launch_args, piped=True)

    def run_gui_mode(self) -> None:
        with contextlib.suppress(Exception):
            from one_dragon.launcher import gui_splash

            # GUI 模式无控制台黑窗（与 RuntimeLauncher._hide_console 同款做法）；
            # 拉起启动图收尾线程：GUI 主窗口就绪后自动收掉 PyInstaller --splash 启动图
            gui_splash.hide_console_window()
            gui_splash.start()
        python_launcher.run_python(["zzz_od", "gui", "app"], no_windows=True)


if __name__ == '__main__':
    launcher = ZLauncher()
    launcher.run()
