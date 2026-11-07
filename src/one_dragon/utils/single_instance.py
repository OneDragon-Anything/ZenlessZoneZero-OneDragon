"""同一工作目录只允许运行一个一条龙实例。

用操作系统文件锁实现：进程存活期间一直持有一字节的独占锁，进程退出（包括崩溃）
时由系统自动释放，不会留下"死锁文件"。锁文件里写入持有者 PID，方便排查。

锁文件建不出来（目录不可写等）和锁被别人占着是两回事：前者要提示目录/权限问题，
后者才提示「已经开了一个」。
"""

import errno
import os
from pathlib import Path

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log

LOCK_FILE_NAME = '.one_dragon.lock'

_instance_lock: 'SingleInstanceLock | None' = None
_last_lock_error: OSError | None = None


class LockBusyError(Exception):
    """锁已被其它实例持有。"""


class SingleInstanceLock:
    """基于文件锁的单实例锁。"""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path: Path = lock_path
        self._file = None

    def acquire(self) -> bool:
        """尝试获取锁。

        Returns:
            获取成功返回 True；已有实例持有时返回 False；锁文件读写失败
            同样返回 False，具体错误记在 `last_error`。
        """
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            # 句柄要一直持有到进程退出，不能 with 自动关闭
            handle = open(self.lock_path, 'a+', encoding='utf-8')  # noqa: SIM115
        except OSError as error:
            self.last_error = error
            log.warning('单实例锁文件无法打开: %s', error)
            return False

        try:
            self._lock_handle(handle)
        except LockBusyError:
            handle.close()
            return False
        except OSError as error:
            self.last_error = error
            log.warning('单实例锁无法加锁: %s', error)
            handle.close()
            return False

        try:
            handle.seek(0)
            handle.truncate()
            handle.write(str(os.getpid()))
            handle.flush()
        except OSError as error:
            self.last_error = error
            log.warning('单实例锁文件写入失败: %s', error)
            handle.close()
            return False

        self._file = handle
        return True

    last_error: OSError | None = None

    def release(self) -> None:
        """释放锁并关闭文件句柄。"""
        handle = self._file
        if handle is None:
            return

        self._file = None
        try:
            self._unlock_handle(handle)
        except Exception:
            pass
        finally:
            handle.close()

    def get_holder_pid(self) -> str:
        """读取锁文件里记录的持有者 PID，读不到返回空串。

        Windows 的文件锁是强制锁，别的句柄读不了被锁住的字节，所以自己持锁时
        必须用同一个句柄读。
        """
        if self._file is not None:
            try:
                self._file.seek(0)
                return self._file.read().strip()
            except OSError:
                return ''

        try:
            return self.lock_path.read_text(encoding='utf-8').strip()
        except OSError:
            return ''

    @staticmethod
    def _lock_handle(handle) -> None:
        """对文件句柄加非阻塞独占锁。

        Raises:
            LockBusyError: 锁已经被别的实例持有
            OSError: 其它加锁失败
        """
        if os.name == 'nt':
            import msvcrt

            # 空文件没有可锁的字节，先补一个占位字节
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(' ')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                if _is_lock_busy(error):
                    raise LockBusyError() from error
                raise
            return

        import fcntl

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if _is_lock_busy(error):
                raise LockBusyError() from error
            raise

    @staticmethod
    def _unlock_handle(handle) -> None:
        """解锁文件句柄。"""
        if os.name == 'nt':
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _is_lock_busy(error: OSError) -> bool:
    """判断加锁失败是不是「已被占用」，而不是权限 / 磁盘错误。"""
    if getattr(error, 'winerror', None) == 33:  # ERROR_LOCK_VIOLATION
        return True
    return error.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK)


def acquire_instance_lock(lock_dir: str | Path | None = None) -> bool:
    """获取当前工作目录的单实例锁。

    Args:
        lock_dir: 锁文件所在目录，默认取工作目录。

    Returns:
        获取成功返回 True；已有实例在运行或锁文件不可写时返回 False。
    """
    global _instance_lock, _last_lock_error
    if _instance_lock is not None:
        return True

    base_dir = Path(lock_dir) if lock_dir is not None else Path(os_utils.get_work_dir())
    lock = SingleInstanceLock(base_dir / LOCK_FILE_NAME)
    if not lock.acquire():
        _last_lock_error = lock.last_error
        return False

    _instance_lock = lock
    _last_lock_error = None
    return True


def get_lock_error() -> OSError | None:
    """返回最近一次单实例锁的真实错误；被别的实例占用时为 None。"""
    return _last_lock_error


def describe_lock_failure() -> str:
    """给用户看的单实例检查失败原因。"""
    if _last_lock_error is not None:
        return (
            '无法创建单实例锁文件，无法启动。\n'
            f'{_last_lock_error}\n'
            '请检查程序目录是否有写入权限，或者换一个目录运行。'
        )
    return (
        '已经有一个一条龙在运行（同一目录只允许开一个）。\n'
        '请先关掉已经打开的窗口，或者切换工作目录后再启动。'
    )


def release_instance_lock() -> None:
    """释放当前进程持有的单实例锁。"""
    global _instance_lock
    if _instance_lock is None:
        return

    _instance_lock.release()
    _instance_lock = None
