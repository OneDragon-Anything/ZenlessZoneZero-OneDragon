import sys

import os
import subprocess

from one_dragon.utils import os_utils


def start_one_dragon(restart: bool) -> None:
    """
    启动一条龙脚本
    :param restart: 是否重启
    :return: 是否成功
    """
    launcher_path = os.path.join(os_utils.get_work_dir(), 'OneDragon-Launcher.exe')
    subprocess.Popen(f'cmd /c "start "" "{launcher_path}""', shell=True)
    if restart:
        sys.exit(0)


def get_launcher_version() -> str:
    """
    检查启动器版本
    :return: 版本号
    """
    launcher_path = os.path.join(os_utils.get_work_dir(), 'OneDragon-Launcher.exe')
    try:
        result = subprocess.run(f'"{launcher_path}" --version', capture_output=True, text=True)
        version_output = result.stdout.strip()
        parts = version_output.split('v', 1)
        return f"v{parts[1]}" if len(parts) > 1 else version_output
    except Exception:
        return ""


if __name__ == '__main__':
    print(get_launcher_version())
