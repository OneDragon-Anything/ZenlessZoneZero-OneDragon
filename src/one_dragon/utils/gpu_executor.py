import threading
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, TypeVar

from one_dragon.utils.log_utils import log
from one_dragon.utils import thread_utils

T = TypeVar("T")
_THREAD_PREFIX = "od_gpu"
_DML_PROVIDER = "DmlExecutionProvider"
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


def should_serialize_providers(providers: Sequence[str] | None) -> bool:
    return providers is not None and _DML_PROVIDER in providers


def create_onnx_session(
        factory: Callable[[], T],
        providers: Sequence[str] | None,
) -> T:
    if should_serialize_providers(providers):
        return run_sync(factory)
    return factory()


def should_serialize_session(session) -> bool:
    try:
        providers = session.get_providers()
    except Exception:
        log.warning('获取ONNX Runtime执行提供程序失败，将保守串行化执行', exc_info=True)
        return True
    return should_serialize_providers(providers)


def run_session(session, output_names, input_feed=None, **kwargs):
    if should_serialize_session(session):
        return run_sync(session.run, output_names, input_feed, **kwargs)
    return session.run(output_names, input_feed, **kwargs)


def shutdown(wait: bool = True) -> None:
    _executor.shutdown(wait=wait)
