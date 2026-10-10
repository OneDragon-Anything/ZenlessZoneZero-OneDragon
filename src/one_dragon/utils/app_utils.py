import os
import re
import subprocess
import sys
from pathlib import Path

from one_dragon.utils import os_utils

ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')

# 启动器 exe 由 PyInstaller 打包，输出编码跟随它自己的控制台代码页，按可能性从高到低尝试
CONSOLE_OUTPUT_ENCODINGS = ('utf-8', 'gbk', 'mbcs')


def decode_console_output(raw: bytes) -> str:
    """
    解码子进程输出的字节流。

    子进程的输出编码由它自己的运行环境决定，与本进程的 locale 无关。本进程处于 UTF-8 模式
    （如设置了 PYTHONUTF8=1）时，subprocess 的 text=True 会按 UTF-8 解码启动器输出的 GBK
    字节并抛 UnicodeDecodeError，导致读不到版本号。

    Args:
        raw: 子进程输出的原始字节。

    Returns:
        str: 解码后的文本；候选编码都失败时用 UTF-8 宽松解码兜底。
    """
    for encoding in CONSOLE_OUTPUT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode('utf-8', errors='replace')


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
        decoded_output = decode_console_output(result.stdout)
        version_output = ANSI_ESCAPE_PATTERN.sub('', decoded_output).strip()
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
