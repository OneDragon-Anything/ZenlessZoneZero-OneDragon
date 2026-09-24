import os
import re
import subprocess
import sys
from pathlib import Path

from one_dragon.utils import os_utils

ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def start_one_dragon(restart: bool) -> None:
    """
    启动一条龙脚本
    :param restart: 是否重启
    :return: 是否成功

    打包运行时（安装器 / 集成启动器）从当前 exe 同目录定位 OneDragon-Launcher.exe
    （发行包中两者并排）；源码运行时从工作目录定位。
    子进程环境设置 PYINSTALLER_RESET_ENVIRONMENT=1：onefile 子 exe 若继承父进程的
    PyInstaller 环境，bootloader 会跳过解压、复用父进程临时目录，父进程退出清理后
    子进程将缺运行时文件（表现为缺 PySide6 pyd 等模块）。
    """
    if getattr(sys, 'frozen', False):
        # 打包运行时（安装器 / 集成启动器），Launcher 与当前 exe 同目录
        launcher_path = Path(sys.executable).resolve().parent / 'OneDragon-Launcher.exe'
    else:
        launcher_path = Path(os_utils.get_work_dir()) / 'OneDragon-Launcher.exe'
    # 子进程不能继承当前 PyInstaller 进程的环境，否则 bootloader 会复用当前进程的
    # 解压临时目录而不重新解压；当前进程退出清理后，子进程会缺运行时文件（如 Qt 的 pyd）
    env = os.environ.copy()
    env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    subprocess.Popen(f'cmd /c "start "" "{launcher_path}""', shell=True, env=env)
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
        env = os.environ.copy()
        # 版本查询无需提权，也不能复用父启动器的 PyInstaller 临时环境
        env.update({
            '__COMPAT_LAYER': 'RunAsInvoker',
            'PYINSTALLER_RESET_ENVIRONMENT': '1',
        })
        result = subprocess.run(
            [exe_path, '--version'],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            env=env,
        )
        version_output = ANSI_ESCAPE_PATTERN.sub('', result.stdout).strip()
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
