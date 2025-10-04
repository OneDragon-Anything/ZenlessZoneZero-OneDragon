from one_dragon.launcher.application_launcher import ApplicationLauncher
from zzz_od.context.zzz_context import ZContext


class ZApplicationLauncher(ApplicationLauncher):
    """绝区零应用启动器"""

    def __init__(self):
        ApplicationLauncher.__init__(self)

    def create_context(self):
        return ZContext()


if __name__ == '__main__':
    launcher = ZApplicationLauncher()
    launcher.run()
