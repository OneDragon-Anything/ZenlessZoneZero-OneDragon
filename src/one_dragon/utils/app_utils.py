import locale
import os
import re
import subprocess
import sys
from pathlib import Path

from one_dragon.launcher.launcher_type import (
    LAUNCHER_EXE,
    RUNTIME_LAUNCHER_EXE,
    detect_running_launcher_type,
)
from one_dragon.utils import os_utils

ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def get_launcher_path() -> Path:
    """获取要启动的启动器 exe 路径。

    当前进程本身就是启动器时直接用它；安装器等其他程序和源码运行时，
    按工作目录里已安装的启动器选择，两种都装了时优先集成启动器。
    """
    if getattr(sys, 'frozen', False) and detect_running_launcher_type() is not None:
        return Path(sys.executable)
    work_dir = Path(os_utils.get_work_dir())
    if (work_dir / RUNTIME_LAUNCHER_EXE).exists():
        return work_dir / RUNTIME_LAUNCHER_EXE
    return work_dir / LAUNCHER_EXE


def start_one_dragon(restart: bool) -> None:
    """启动独立的一条龙进程，重启时在创建进程成功后退出当前程序。"""
    launcher_path = get_launcher_path()
    env = os.environ.copy()
    # 重启进程必须重新初始化 PyInstaller，不能复用即将退出的父进程环境。
    env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    subprocess.Popen(
        [str(launcher_path)],
        cwd=os_utils.get_work_dir(),
        env=env,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
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
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            env=env,
        )
        # 打包后的启动器可能按系统本地编码输出，不应受父进程 UTF-8 模式影响。
        try:
            version_output = result.stdout.decode('utf-8')
        except UnicodeDecodeError:
            version_output = result.stdout.decode(locale.getencoding())
        version_output = ANSI_ESCAPE_PATTERN.sub('', version_output).strip()
        return version_output.rsplit(maxsplit=1)[-1] if version_output else ""
    except Exception:
        return ""


def get_launcher_version() -> str:
    """
    检查当前启动器版本
    Returns:
        str: 版本号
    """
    return get_exe_version(str(get_launcher_path()))


if __name__ == '__main__':
    print(get_launcher_version())
