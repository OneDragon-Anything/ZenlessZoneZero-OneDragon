from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, ClassVar

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_def import OperationDef
from zzz_od.auto_battle.atomic_op.btn_common import BtnRunStatus

if TYPE_CHECKING:
    from zzz_od.auto_battle.auto_battle_context import AutoBattleContext


class AtomicBtnQuickAssist(AtomicOp):

    OP_NAME: ClassVar[str] = '按键-快速支援'

    def __init__(self, ctx: AutoBattleContext, op_def: OperationDef):
        self.ctx: AutoBattleContext = ctx

        self.pre_delay: float = op_def.pre_delay
        self.post_delay: float = op_def.post_delay

        AtomicOp.__init__(self, op_name=AtomicBtnQuickAssist.OP_NAME)

        self._status = BtnRunStatus.WAIT
        self._update_lock = threading.Lock()

    def execute(self):
        with self._update_lock:
            if self._status != BtnRunStatus.WAIT:
                return
            self._status = BtnRunStatus.RUNNING

        if self._status == BtnRunStatus.RUNNING and self.pre_delay > 0:
            time.sleep(self.pre_delay)

        if self._status == BtnRunStatus.RUNNING:
            self.ctx.quick_assist()

        if self._status == BtnRunStatus.RUNNING and self.post_delay > 0:
            time.sleep(self.post_delay)

        with self._update_lock:
            self._status = BtnRunStatus.WAIT

    def stop(self) -> None:
        with self._update_lock:
            self._status = BtnRunStatus.STOP
