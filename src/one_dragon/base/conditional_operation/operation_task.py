from concurrent.futures import ThreadPoolExecutor, Future

from threading import Lock
from typing import Optional, List, Set

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.utils import thread_utils
from one_dragon.utils.log_utils import log

_od_op_task_executor = ThreadPoolExecutor(thread_name_prefix='_od_op_task_executor', max_workers=32)


class OperationTask:

    def __init__(self, op_list: List[AtomicOp]):
        """
        包含一串指令的任务
        :param op_list:
        """
        self.trigger: Optional[str] = None  # 触发器
        self.interrupt_states: Set[str] = set()  # 可被打断的状态
        self.is_trigger: bool = False  # 是否触发器场景
        self.priority: Optional[int] = None  # 优先级 只能被高等级的打断；为None时可以被随意打断

        self.op_list: List[AtomicOp] = op_list
        self.running: bool = False
        self._current_op: Optional[AtomicOp] = None  # 当前执行的指令
        self._async_ops: List[AtomicOp] = []  # 执行过异步操作
        self._op_lock: Lock = Lock()  # 操作锁 用于保证stop里的一定是最后执行的op

        self.expr_list: List[str] = []  # 用于界面显示
        self.debug_name_list: List[str] = []  # 用于调试显示，存储yml中的debug_name

    @property
    def debug_name_display(self) -> str:
        # 创建一个新的列表，处理空元素
        processed_list = ['[ ]' if not name or name.strip() == '' else name for name in self.debug_name_list]
        return ' ← '.join(processed_list) if processed_list else '/'

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

    def add_expr(self, expr: str, debug_name: Optional[str] = None) -> None:
        """
        添加一个表达式及其调试名称
        :param expr: 表达式
        :param debug_name: 调试名称
        :return:
        """
        self.expr_list.append(expr)
        self.debug_name_list.append(debug_name or '')

    def set_priority(self, priority: Optional[int]) -> None:
        """
        设置触发的场景信息
        :param priority: 场景优先级
        :return:
        """
        self.priority = priority

    def set_trigger(self, trigger: Optional[str]) -> None:
        """
        设置触发的场景信息
        :param trigger: 触发场景
        :return:
        """
        self.trigger = trigger
        self.is_trigger = trigger is not None and trigger != ''

    def add_interrupt_states(self, interrupt_states: Set[str]) -> None:
        """
        添加可打断的场景
        :param interrupt_states: 可以被打断的状态
        :return:
        """
        if interrupt_states is not None:
            self.interrupt_states.update(interrupt_states)

    @property
    def expr_display(self) -> str:
        # 创建一个新的列表，处理空元素
        processed_list = []
        for expr, debug_name in zip(self.expr_list, self.debug_name_list):
            if not debug_name or debug_name.strip() == '':
                # 如果debug名为空，使用状态名
                display_name = '[ ]' if not expr or expr.strip() == '' else expr
            else:
                # 否则使用debug名
                display_name = debug_name
            processed_list.append(display_name)
        return ' ← '.join(processed_list) if processed_list else '/'

    @property
    def priority_display(self) -> str:
        return '无优先级' if self.priority is None else str(self.priority)

    @property
    def trigger_display(self) -> str:
        return '主循环' if self.trigger is None else self.trigger