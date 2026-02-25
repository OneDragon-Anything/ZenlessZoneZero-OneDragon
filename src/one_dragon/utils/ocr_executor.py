from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import threading
from typing import Callable, TypeVar

from one_dragon.utils import thread_utils
from one_dragon.utils.log_utils import log

_THREAD_PREFIX = "od_ocr"
_DEFAULT_RUN_SYNC_TIMEOUT_SECONDS = 60.0
_executor_local = threading.local()
T = TypeVar("T")


class OCRTimeoutError(TimeoutError):
    """OCR executor timed out while waiting for result."""
    pass


def _mark_executor_thread() -> None:
    _executor_local.is_ocr_executor_thread = True


_executor = ThreadPoolExecutor(
    thread_name_prefix=_THREAD_PREFIX,
    max_workers=1,
    initializer=_mark_executor_thread,
)


def is_executor_thread() -> bool:
    return bool(getattr(_executor_local, "is_ocr_executor_thread", False))


def _submit_internal(fn: Callable[..., T], with_callback: bool, /, *args, **kwargs) -> Future[T]:
    f = _executor.submit(fn, *args, **kwargs)
    if with_callback:
        f.add_done_callback(thread_utils.handle_future_result)
    return f


def submit(fn: Callable[..., T], /, *args, **kwargs) -> Future[T]:
    return _submit_internal(fn, True, *args, **kwargs)


def run_sync(fn: Callable[..., T], /, *args, timeout: float | None = _DEFAULT_RUN_SYNC_TIMEOUT_SECONDS, **kwargs) -> T:
    if is_executor_thread():
        return fn(*args, **kwargs)
    f = _submit_internal(fn, False, *args, **kwargs)
    try:
        return f.result(timeout=timeout)
    except FutureTimeoutError as e:
        cancelled = f.cancel()
        log.warning(
            "OCR task timeout after %.2fs; cancel=%s running=%s done=%s future=%r",
            timeout if timeout is not None else -1.0,
            cancelled,
            f.running(),
            f.done(),
            f,
        )
        raise OCRTimeoutError(f"OCR task timed out after {timeout} seconds") from e


def shutdown(wait: bool = True):
    _executor.shutdown(wait=wait)
