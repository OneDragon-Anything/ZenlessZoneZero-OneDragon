from __future__ import annotations

import threading
import time
from typing import ClassVar
from typing import TYPE_CHECKING

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_def import OperationDef
from zzz_od.auto_battle.atomic_op.btn_common import BtnRunStatus

if TYPE_CHECKING:
    from zzz_od.auto_battle.auto_battle_context import AutoBattleContext


class AtomicBtnSwitchAgent(AtomicOp):

    OP_NAME: ClassVar[str] = '按键-切换角色'

    def __init__(self, ctx: AutoBattleContext, op_def: OperationDef):
        self.ctx: AutoBattleContext = ctx
        self.agent_name: str = op_def.original_data.get('agent_name')
        if self.agent_name is None:
            raise ValueError('未指定代理人名称 agent_name为空')

        self.pre_delay: float = op_def.pre_delay
        self.post_delay: float = op_def.post_delay

        AtomicOp.__init__(self, op_name='%s %s' % (AtomicBtnSwitchAgent.OP_NAME, self.agent_name))

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
            self.ctx.switch_by_name(self.agent_name)

        if self._status == BtnRunStatus.RUNNING and self.post_delay > 0:
            time.sleep(self.post_delay)

        with self._update_lock:
            self._status = BtnRunStatus.WAIT

    def stop(self) -> None:
        with self._update_lock:
            self._status = BtnRunStatus.STOP
