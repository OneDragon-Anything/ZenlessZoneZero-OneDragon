from concurrent.futures import ThreadPoolExecutor, Future
from collections.abc import Callable
from typing import ParamSpec, TypeVar
from one_dragon.utils import thread_utils

# 限制只能有一个方法访问gpu 避免gpu资源竞争崩溃
_executor = ThreadPoolExecutor(thread_name_prefix='od_gpu', max_workers=1)

P = ParamSpec('P')
R = TypeVar('R')


def submit(fn: Callable[P], /, *args: P.args, **kwargs: P.kwargs) -> Future:
    f = _executor.submit(fn, *args, **kwargs)
    f.add_done_callback(thread_utils.handle_future_result)

    return f


# 给 submit 包一层, 以简化调用写法
def execute_function(is_use_gpu, fn: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs) -> R:
    if is_use_gpu:
        f = submit(fn, *args, **kwargs)
        return f.result()
    else:
        return fn(*args, **kwargs)


def shutdown(wait: bool = True):
    _executor.shutdown(wait=wait)