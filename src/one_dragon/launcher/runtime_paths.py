"""集成启动器运行时目录的路径与替换。

集成启动器运行时，Python 解释器本身就是从 `.runtime` 加载的，进程活着的时候
既不能改名也不能替换这个目录（Windows 报 WinError 5 拒绝访问）。所以更新时新
运行时先落到 `.runtime.new`，再由一个独立的批处理在本次进程退出后完成替换。
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

from one_dragon.utils.log_utils import log

RUNTIME_DIR = '.runtime'
RUNTIME_DIR_NEW = '.runtime.new'
RUNTIME_DIR_BACKUP = '.runtime.bak'
SWAP_SCRIPT_NAME = 'apply_runtime_update.bat'

# 等进程退出、再把 .runtime.new 换成 .runtime 的批处理
SWAP_SCRIPT_CONTENT = """@echo off
setlocal
set "TARGET_PID=%~1"
:wait
tasklist /FI "PID eq %TARGET_PID%" /NH 2>nul | find "%TARGET_PID%" >nul
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait
)
if exist ".runtime" rmdir /s /q ".runtime.bak" >nul 2>&1
if exist ".runtime" ren ".runtime" ".runtime.bak"
if errorlevel 1 exit /b 1
if exist ".runtime.new" ren ".runtime.new" ".runtime"
if errorlevel 1 (
  ren ".runtime.bak" ".runtime" >nul 2>&1
  exit /b 1
)
del "%~f0" >nul 2>&1
exit /b 0
"""


def has_staged_runtime(work_dir: Path) -> bool:
    """是否还有等待替换的新运行时目录。"""
    return (work_dir / RUNTIME_DIR_NEW).is_dir()


def write_swap_script(work_dir: Path) -> Path:
    """写好退出后替换运行时的批处理，返回脚本路径。"""
    script_path = work_dir / SWAP_SCRIPT_NAME
    script_path.write_bytes(
        SWAP_SCRIPT_CONTENT.encode("utf-8").replace(bytes([10]), bytes([13, 10]))
    )
    return script_path


def schedule_runtime_swap(work_dir: Path, pid: int) -> bool:
    """安排当前进程退出后替换 `.runtime`。

    解释器还在跑的时候替换不了运行时目录，交给独立进程等待退出后再换。

    Args:
        work_dir: 程序目录
        pid: 需要等待退出的进程号

    Returns:
        bool: 是否成功启动替换脚本
    """
    if not has_staged_runtime(work_dir):
        return False

    try:
        script_path = write_swap_script(work_dir)
        subprocess.Popen(
            [str(script_path), str(pid)],
            cwd=str(work_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=_detached_flags(),
        )
    except OSError:
        log.error('启动运行时替换脚本失败', exc_info=True)
        return False

    log.info('已安排退出后替换运行时目录')
    return True


def _detached_flags() -> int:
    """返回后台运行所需的进程创建标志。"""
    if sys.platform != 'win32':
        return 0
    return (
        getattr(subprocess, 'DETACHED_PROCESS', 0)
        | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    )


def runtime_dirs_equal(left: Path, right: Path) -> bool:
    """比较两个运行时目录的文件内容是否一致。

    发布包版本号变了不代表运行时文件也变了（PyInstaller 的 `_internal` 经常原样
    复用）。先比相对路径和文件大小，大小全一致时才逐个算 sha256，避免没必要地
    替换整个目录。

    Args:
        left: 目录一
        right: 目录二

    Returns:
        bool: 两个目录的文件集合与内容都一致
    """
    left_files = _runtime_file_sizes(left)
    right_files = _runtime_file_sizes(right)
    if left_files != right_files:
        return False

    for relative_path in left_files:
        if _file_sha256(left / relative_path) != _file_sha256(right / relative_path):
            return False
    return True


def _runtime_file_sizes(root: Path) -> dict[str, int]:
    """列出目录里所有文件的相对路径和大小。"""
    result: dict[str, int] = {}
    if not root.is_dir():
        return result
    for path in root.rglob('*'):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.stat().st_size
    return result


def _file_sha256(path: Path) -> str:
    """算单个文件的 sha256。"""
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def stage_runtime_dir(staged_runtime: Path, work_dir: Path) -> None:
    """把下载好的新运行时放到 `.runtime.new`，等进程退出后替换。

    Args:
        staged_runtime: 解压好的新运行时目录
        work_dir: 程序目录
    """
    target = work_dir / RUNTIME_DIR_NEW
    if target.exists():
        shutil.rmtree(target)
    staged_runtime.rename(target)


def clear_staged_runtime_dir(work_dir: Path) -> None:
    """删除还没生效的新运行时目录（更新回滚时用）。

    Args:
        work_dir: 程序目录
    """
    target = work_dir / RUNTIME_DIR_NEW
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
