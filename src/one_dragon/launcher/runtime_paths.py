"""集成启动器运行时目录的路径与替换。

集成启动器运行中无法给 `.runtime` 改名：进程把它当运行时目录，目录里还有加载中的
DLL，Windows 会报 WinError 5 拒绝访问。所以更新时新运行时先落到 `.runtime.new`，
等下次启动、Python 还没加载运行时时再换进来。
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from one_dragon.utils.log_utils import log

RUNTIME_DIR = '.runtime'
RUNTIME_DIR_NEW = '.runtime.new'
RUNTIME_DIR_BACKUP = '.runtime.bak'


def apply_staged_runtime_dir(work_dir: Path) -> bool:
    """把 `.runtime.new` 换成当前 `.runtime`。

    只能在启动早期、Python 运行时还没加载时调用。旧 `.runtime` 先改名成
    `.runtime.bak` 留作回滚；新目录换不进去时把旧目录换回来，保证启动不会因为
    更新留下坏目录而失败。

    Args:
        work_dir: 程序目录

    Returns:
        bool: 是否完成了替换；没有待替换的目录或替换失败时返回 False
    """
    staged = work_dir / RUNTIME_DIR_NEW
    if not staged.is_dir():
        return False

    runtime = work_dir / RUNTIME_DIR
    backup = work_dir / RUNTIME_DIR_BACKUP
    try:
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        if runtime.is_dir():
            runtime.rename(backup)
    except OSError:
        log.error('旧运行时目录无法改名，继续使用当前版本', exc_info=True)
        return False

    try:
        staged.rename(runtime)
    except OSError:
        log.error('新运行时目录切换失败，回滚到旧版本', exc_info=True)
        if not runtime.is_dir() and backup.is_dir():
            try:
                backup.rename(runtime)
            except OSError:
                log.error('回滚旧运行时目录失败，请重新安装', exc_info=True)
        return False

    log.info('已切换到新版本的运行时')
    return True


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
    """把下载好的新运行时放到 `.runtime.new`，等下次启动再替换。

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
