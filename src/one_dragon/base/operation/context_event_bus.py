from concurrent.futures import ThreadPoolExecutor, Future

from typing import Callable, Any, List

from one_dragon.utils import thread_utils

_od_event_bus_executor = ThreadPoolExecutor(thread_name_prefix='od_event_bus', max_workers=32)


class ContextEventItem:

    def __init__(self, event_id: str, data: Any):
        self.event_id: str = event_id
        self.data: Any = data


class ContextEventBus:

    def __init__(self):
        self.callbacks: dict[str, List[Callable[[Any], None]]] = {}

    def dispatch_event(self, event_id: str, event_obj: Any = None):
        """
        下发事件
        :param event_id: 事件ID
        :param event_obj: 事件体
        :return:
        """
        if event_id not in self.callbacks:
            return
        for callback in self.callbacks[event_id]:
            future: Future = _od_event_bus_executor.submit(callback, ContextEventItem(event_id, event_obj))
            future.add_done_callback(thread_utils.handle_future_result)

    def listen_event(self, event_id: str, callback: Callable[[ContextEventItem], None]):
        """
        新增监听事件
        监听的回调，如果耗时过长，应该在自己的线程池的工作，避免阻塞
        :param event_id:
        :param callback:
        :return:
        """
        if event_id not in self.callbacks:
            self.callbacks[event_id] = []
        existed_callbacks = self.callbacks[event_id]
        if callback not in existed_callbacks:
            existed_callbacks.append(callback)

    def unlisten_event(self, event_id: str, callback: Callable[[Any], None]):
        """
        解除一个事件的监听
        :param event_id:
        :param callback:
        :return:
        """
        if event_id not in self.callbacks:
            return
        try:
            self.callbacks[event_id].remove(callback)
        except Exception as e:
            pass

    def unlisten_all_event(self, obj: Any):
        """
        解除一个对象的所有监听
        :param obj:
        :return:
        """
        to_remove = {}
        for key, existed_callbacks in self.callbacks.items():
            to_remove[key] = []
            for existed in existed_callbacks:
                if id(existed.__self__) == id(obj):
                    to_remove[key].append(existed)

        for key, removes in to_remove.items():
            for remove in removes:
                self.callbacks[key].remove(remove)

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        @return:
        """
        _od_event_bus_executor.shutdown(wait=False, cancel_futures=True)
