from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import List, Optional

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.utils import thread_utils
from one_dragon.utils.log_utils import log

# 当前执行1个 新的打断1个 即理论最多2个同时运行
_od_op_task_executor = ThreadPoolExecutor(thread_name_prefix='_od_op_task_executor', max_workers=4)


class OperationExecutor:

    def __init__(
        self,
        op_list: list[AtomicOp],
        trigger_time: float,
    ):
        """
        指令执行器 用于管理如何执行/终止一串指令
        """
        self.op_list: List[AtomicOp] = op_list
        self.trigger_time: float = trigger_time  # 触发时间

        self.running: bool = False
        self._current_op: Optional[AtomicOp] = None  # 当前执行的指令
        self._async_ops: List[AtomicOp] = []  # 执行过异步操作
        self._op_lock: Lock = Lock()  # 操作锁 用于保证stop里的一定是最后执行的op

    def run_async(self) -> Future:
        """
        异步执行
        :return:
        """
        self.running = True
        future: Future = _od_op_task_executor.submit(self._run)
        future.add_done_callback(thread_utils.handle_future_result)
        return future

    def _run(self) -> bool:
        """
        执行
        :return: 是否完成所有指令了
        """
        for idx in range(len(self.op_list)):
            with self._op_lock:
                if not self.running:
                    # 被stop中断了 不继续后续的操作
                    break
                self._current_op = self.op_list[idx]
                if self._current_op.async_op:
                    self._async_ops.append(self._current_op)
                future: Future = _od_op_task_executor.submit(self._current_op.execute)
                future.add_done_callback(thread_utils.handle_future_result)

            try:
                future.result()
            except Exception:
                log.error('指令执行出错', exc_info=True)

            with self._op_lock:
                if not self.running:
                    # 被stop中断了 那么应该认为这个op没有执行完 不进行后续判断
                    break
                self._current_op = None
                if self.running and idx == len(self.op_list) - 1:
                    self.running = False
                    return True

        return False

    def stop(self) -> bool:
        """
        停止运行
        :return: 停止前是否已经完成所有指令了
        """
        with self._op_lock:
            if not self.running:
                # _run里面已经把op执行完了 就不需要额外的停止操作了
                self._current_op = None
                self._async_ops.clear()
                return True

            self.running = False
            if self._current_op is not None:
                self._current_op.stop()
                self._current_op = None
            for op in self._async_ops:
                op.stop()
            self._async_ops.clear()
            return False

    @staticmethod
    def after_app_shutdown() -> None:
        """
        整个脚本运行结束后的清理
        """
        _od_op_task_executor.shutdown(wait=False, cancel_futures=True)
