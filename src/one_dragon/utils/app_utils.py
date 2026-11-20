import locale
import os
import re
import subprocess
import sys
from pathlib import Path

from one_dragon.utils import os_utils

ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def start_one_dragon(restart: bool) -> None:
    """启动独立的一条龙进程，重启时在创建进程成功后退出当前程序。"""
    if getattr(sys, 'frozen', False):
        launcher_path = Path(sys.executable)
    else:
        launcher_path = Path(os_utils.get_work_dir()) / 'OneDragon-Launcher.exe'
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
    """检查本次运行所用启动器的版本。

    源码运行时没有随本次运行一起打包的启动器，工作目录里的 exe 只是别的启动器留下的文件，
    读它会把不相干的版本号当成当前版本，所以直接返回空。

    Returns:
        str: 版本号，源码运行或读取失败时为空字符串
    """
    if not getattr(sys, 'frozen', False):
        return ''

    return get_exe_version(str(Path(sys.executable)))


if __name__ == '__main__':
    print(get_launcher_version())
