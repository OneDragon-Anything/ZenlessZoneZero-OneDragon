from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from zzz_od.auto_battle.auto_battle_state import BattleStateEnum

if TYPE_CHECKING:
    from zzz_od.auto_battle.auto_battle_context import AutoBattleContext


class AtomicBtnMoveA(AtomicOp):

    def __init__(self, ctx: AutoBattleContext, press: bool = False, press_time: Optional[float] = None, release: bool = False):
        if press:
            op_name = BattleStateEnum.BTN_MOVE_A.value + '按下'
        elif release:
            op_name = BattleStateEnum.BTN_MOVE_A.value + '松开'
        else:
            op_name = BattleStateEnum.BTN_MOVE_A.value
        AtomicOp.__init__(self, op_name=op_name, async_op=press and press_time is None)
        self.ctx: AutoBattleContext = ctx
        self.press: bool = press
        self.press_time: Optional[float] = press_time
        self.release: bool = release

    def execute(self):
        self.ctx.move_a(self.press, self.press_time, self.release)

    def stop(self) -> None:
        if self.press:
            self.ctx.move_a(release=True)
