from concurrent.futures import Future, ThreadPoolExecutor
import threading
from typing import Callable, TypeVar, ParamSpec

from one_dragon.utils import thread_utils

P = ParamSpec('P')
T = TypeVar("T")
_THREAD_PREFIX = "od_gpu"
_executor_local = threading.local()


def _mark_executor_thread() -> None:
    _executor_local.is_gpu_executor_thread = True


# 限制只能有一个方法访问 DirectML GPU 避免多 session 并发崩溃
_executor = ThreadPoolExecutor(
    thread_name_prefix=_THREAD_PREFIX,
    max_workers=1,
    initializer=_mark_executor_thread,
)


def is_executor_thread() -> bool:
    return bool(getattr(_executor_local, "is_gpu_executor_thread", False))


def submit(fn: Callable[..., T], /, *args, **kwargs) -> Future[T]:
    f = _executor.submit(fn, *args, **kwargs)
    f.add_done_callback(thread_utils.handle_future_result)
    return f


def run_sync(fn: Callable[..., T], /, *args, **kwargs) -> T:
    if is_executor_thread():
        return fn(*args, **kwargs)
    return submit(fn, *args, **kwargs).result()


def should_serialize_session(session) -> bool:
    try:
        providers = session.get_providers()
    except Exception:
        return False
    return "DmlExecutionProvider" in providers


def run_session(session, output_names, input_feed=None, **kwargs):
    if should_serialize_session(session):
        return run_sync(session.run, output_names, input_feed, **kwargs)
    return session.run(output_names, input_feed, **kwargs)


def shutdown(wait: bool = True) -> None:
    _executor.shutdown(wait=wait)


# 先判断是否使用gpu, 然后执行函数
def execute_function(is_use_gpu, fn: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    if is_use_gpu:
        return run_sync(fn, *args, **kwargs)
    else:
        return fn(*args, **kwargs)