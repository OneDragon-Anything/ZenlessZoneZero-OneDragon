import threading
from typing import ClassVar

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_def import OperationDef


class AtomicWait(AtomicOp):

    OP_NAME: ClassVar[str] = '等待秒数'

    def __init__(self, op_def: OperationDef):
        wait_seconds = op_def.wait_seconds
        if op_def.data is not None and len(op_def.data) > 0:
            wait_seconds = float(op_def.data[0])
        AtomicOp.__init__(self, op_name=f'{AtomicWait.OP_NAME} {wait_seconds:.2f}')
        self.wait_seconds: float = wait_seconds
        self._stop_event = threading.Event()  # 用于中断的Event

    def execute(self):
        self._stop_event.clear()
        # 使用 wait() 而不是 sleep()，这样可以被 stop() 中断
        self._stop_event.wait(timeout=self.wait_seconds)

    def stop(self):
        # 中断等待
        self._stop_event.set()
