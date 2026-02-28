import sys

from one_dragon.launcher.application_launcher import ApplicationLauncher
from zzz_od.context.zzz_context import ZContext


class ZApplicationLauncher(ApplicationLauncher):
    """绝区零应用启动器"""

    def __init__(self):
        ApplicationLauncher.__init__(self)

    def create_context(self):
        return ZContext()


def main(args: list[str] | None = None) -> None:
    if args is not None:
        sys.argv = [sys.argv[0]] + args
    launcher = ZApplicationLauncher()
    launcher.run()


if __name__ == '__main__':
    main()
