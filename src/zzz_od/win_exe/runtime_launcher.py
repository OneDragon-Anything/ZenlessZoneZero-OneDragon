from collections.abc import Callable


def run_onedragon(
    launch_args: list[str],
    on_ready: Callable[[], None],
) -> int:
    """从当前选中的源码树运行一条龙。"""
    from zzz_od.application.zzz_application_launcher import main

    return main(launch_args, on_ready=on_ready)


def run_gui(on_ready: Callable[[], None]) -> int:
    """从当前选中的源码树运行图形界面。"""
    from zzz_od.gui.app import main

    return main(on_ready=on_ready)
