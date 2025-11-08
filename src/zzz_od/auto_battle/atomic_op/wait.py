import time
from typing import ClassVar

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_def import OperationDef


class AtomicWait(AtomicOp):

    OP_NAME: ClassVar[str] = '等待秒数'

    def __init__(self, op_def: OperationDef):
        wait_seconds = op_def.wait_seconds
        if op_def.data is not None:
            if len(op_def.data) > 0:
                wait_seconds = float(op_def.data[0])
        AtomicOp.__init__(self, op_name='%s %.2f' % (AtomicWait.OP_NAME, wait_seconds))
        self.wait_seconds: float = wait_seconds

    def execute(self):
        time.sleep(self.wait_seconds)
