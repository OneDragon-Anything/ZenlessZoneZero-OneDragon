from concurrent.futures import ThreadPoolExecutor, Future

from one_dragon.utils import thread_utils

# 限制只能有一个方法访问gpu 避免gpu资源竞争崩溃
_executor = ThreadPoolExecutor(thread_name_prefix='od_gpu', max_workers=1)


def submit(fn, /, *args, **kwargs) -> Future:
    f = _executor.submit(fn, *args, **kwargs)
    f.add_done_callback(thread_utils.handle_future_result)

    return f
