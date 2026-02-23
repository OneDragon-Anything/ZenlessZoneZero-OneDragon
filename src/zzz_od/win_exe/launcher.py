from one_dragon.devtools import python_launcher
from one_dragon.launcher.exe_launcher import ExeLauncher
from one_dragon.version import __version__


class ZLauncher(ExeLauncher):
    """绝区零启动器"""

    def __init__(self):
        ExeLauncher.__init__(self, "绝区零 一条龙 启动器", __version__)

    def run_onedragon_mode(self, launch_args) -> None:
        python_launcher.run_python(["zzz_od", "application", "zzz_application_launcher.py"], no_windows=False, args=launch_args, piped=True)

    def run_gui_mode(self) -> None:
        python_launcher.run_python(["zzz_od", "gui", "app.py"], no_windows=True)


if __name__ == '__main__':
    launcher = ZLauncher()
    launcher.run()
