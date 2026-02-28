import subprocess
import sys
from pathlib import Path

from one_dragon.utils import os_utils


def start_one_dragon(restart: bool) -> None:
    """
    启动一条龙脚本
    :param restart: 是否重启
    :return: 是否成功
    """
    if getattr(sys, 'frozen', False):
        launcher_path = Path(sys.executable)
    else:
        launcher_path = Path(os_utils.get_work_dir()) / 'OneDragon-Launcher.exe'
    subprocess.Popen(f'cmd /c "start "" "{launcher_path}""', shell=True)
    if restart:
        sys.exit(0)


def get_exe_version(exe_path: str) -> str:
    """
    获取指定 exe 的版本号（通过 --version 参数）
    Args:
        exe_path: exe 文件路径
    Returns:
        str: 版本号，失败返回空字符串
    """
    try:
        result = subprocess.run(
            f'"{exe_path}" --version',
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        version_output = result.stdout.strip()
        return version_output.rsplit(maxsplit=1)[-1] if version_output else ""
    except Exception:
        return ""


def get_launcher_version() -> str:
    """
    检查当前启动器版本
    Returns:
        str: 版本号
    """
    if getattr(sys, 'frozen', False):
        launcher_path = Path(sys.executable)
    else:
        launcher_path = Path(os_utils.get_work_dir()) / 'OneDragon-Launcher.exe'
    return get_exe_version(str(launcher_path))


if __name__ == '__main__':
    print(get_launcher_version())
