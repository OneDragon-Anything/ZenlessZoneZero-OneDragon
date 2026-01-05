from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.conditional_operation.atomic_op import AtomicOp

if TYPE_CHECKING:
    from zzz_od.auto_battle.auto_battle_context import AutoBattleContext


class AtomicTurn(AtomicOp):

    def __init__(self, ctx: AutoBattleContext, turn_x: float):
        AtomicOp.__init__(self, op_name='转向', async_op=False)
        self.ctx: AutoBattleContext = ctx
        self.turn_x: float = turn_x

    def execute(self):
        self.ctx.ctx.controller.turn_by_distance(self.turn_x)

    def stop(self) -> None:
        pass
