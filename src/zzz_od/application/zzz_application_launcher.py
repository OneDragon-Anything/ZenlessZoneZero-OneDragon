import sys
from collections.abc import Callable

from one_dragon.launcher.application_launcher import ApplicationLauncher
from zzz_od.context.zzz_context import ZContext


class ZApplicationLauncher(ApplicationLauncher):
    """绝区零应用启动器。"""

    def __init__(self, on_ready: Callable[[], None] | None = None) -> None:
        ApplicationLauncher.__init__(self, on_ready=on_ready)

    def create_context(self) -> ZContext:
        return ZContext()


def main(
    args: list[str] | None = None,
    on_ready: Callable[[], None] | None = None,
) -> int:
    """运行一条龙；集成启动器可接收 ready 回调。"""
    if args is not None:
        sys.argv = [sys.argv[0], *args]
    launcher = ZApplicationLauncher(on_ready=on_ready)
    launcher.run()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
