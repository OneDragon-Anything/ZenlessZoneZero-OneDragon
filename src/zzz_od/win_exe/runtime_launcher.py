from one_dragon.launcher.runtime_launcher import RuntimeLauncher
from one_dragon.version import __version__


class ZLauncher(RuntimeLauncher):
    """绝区零启动器"""

    def __init__(self) -> None:
        RuntimeLauncher.__init__(self, "绝区零 一条龙 启动器", __version__)

    def _do_run_onedragon(self, launch_args: list[str]) -> None:
        from zzz_od.application.zzz_application_launcher import main
        main(launch_args)

    def _do_run_gui(self) -> None:
        from zzz_od.gui.app import main
        main()


if __name__ == '__main__':
    launcher = ZLauncher()
    launcher.run()
