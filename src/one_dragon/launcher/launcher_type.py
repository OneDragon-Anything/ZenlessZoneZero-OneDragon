import sys
from pathlib import Path
from typing import Literal

LauncherType = Literal['launcher', 'runtime']

LAUNCHER_EXE = 'OneDragon-Launcher.exe'
RUNTIME_LAUNCHER_EXE = 'OneDragon-RuntimeLauncher.exe'


def detect_running_launcher_type() -> LauncherType | None:
    """检测当前正在运行的启动器类型。"""
    if not getattr(sys, 'frozen', False):
        return 'launcher'

    exe_name = Path(sys.executable).name
    if exe_name == RUNTIME_LAUNCHER_EXE:
        return 'runtime'
    if exe_name == LAUNCHER_EXE:
        return 'launcher'
    return None
