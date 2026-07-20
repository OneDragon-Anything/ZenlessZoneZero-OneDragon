from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from zzz_od.auto_battle.auto_battle_state import BattleStateEnum

if TYPE_CHECKING:
    from zzz_od.auto_battle.auto_battle_context import AutoBattleContext


class AtomicBtnSwitchBackup(AtomicOp):

    def __init__(self, ctx: AutoBattleContext, press: bool = False, press_time: float | None = None, release: bool = False):
        if press:
            op_name = BattleStateEnum.BTN_SWITCH_BACKUP.value + '按下'
        elif release:
            op_name = BattleStateEnum.BTN_SWITCH_BACKUP.value + '松开'
        else:
            op_name = BattleStateEnum.BTN_SWITCH_BACKUP.value
        AtomicOp.__init__(self, op_name=op_name, async_op=press and press_time is None)
        self.ctx: AutoBattleContext = ctx
        self.press: bool = press
        self.press_time: float | None = press_time
        self.release: bool = release

    def execute(self) -> None:
        self.ctx.switch_backup(self.press, self.press_time, self.release)

    def stop(self) -> None:
        if self.press:
            self.ctx.switch_backup(release=True)
