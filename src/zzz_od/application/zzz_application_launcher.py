from one_dragon.launcher.application_launcher import ApplicationLauncher
from zzz_od.application.zzz_one_dragon_app import ZOneDragonApp
from zzz_od.context.zzz_context import ZContext


class ZApplicationLauncher(ApplicationLauncher):
    """绝区零应用启动器"""

    def create_context(self):
        return ZContext()

    def get_app_class(self):
        return ZOneDragonApp


if __name__ == '__main__':
    launcher = ZApplicationLauncher()
    launcher.run()
