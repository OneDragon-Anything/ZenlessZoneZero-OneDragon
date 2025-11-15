from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from one_dragon.base.conditional_operation.operation_def import OperationDef
from zzz_od.auto_battle.atomic_op.btn_chain_cancel import AtomicBtnChainCancel
from zzz_od.auto_battle.atomic_op.btn_chain_left import AtomicBtnChainLeft
from zzz_od.auto_battle.atomic_op.btn_chain_right import AtomicBtnChainRight
from zzz_od.auto_battle.atomic_op.btn_common import AtomicBtnCommon
from zzz_od.auto_battle.atomic_op.btn_dodge import AtomicBtnDodge
from zzz_od.auto_battle.atomic_op.btn_lock import AtomicBtnLock
from zzz_od.auto_battle.atomic_op.btn_move_a import AtomicBtnMoveA
from zzz_od.auto_battle.atomic_op.btn_move_d import AtomicBtnMoveD
from zzz_od.auto_battle.atomic_op.btn_move_s import AtomicBtnMoveS
from zzz_od.auto_battle.atomic_op.btn_move_w import AtomicBtnMoveW
from zzz_od.auto_battle.atomic_op.btn_normal_attack import AtomicBtnNormalAttack
from zzz_od.auto_battle.atomic_op.btn_quick_assist import AtomicBtnQuickAssist
from zzz_od.auto_battle.atomic_op.btn_special_attack import AtomicBtnSpecialAttack
from zzz_od.auto_battle.atomic_op.btn_switch_agent import AtomicBtnSwitchAgent
from zzz_od.auto_battle.atomic_op.btn_switch_next import AtomicBtnSwitchNext
from zzz_od.auto_battle.atomic_op.btn_switch_prev import AtomicBtnSwitchPrev
from zzz_od.auto_battle.atomic_op.btn_ultimate import AtomicBtnUltimate
from zzz_od.auto_battle.atomic_op.state_clear import AtomicClearState
from zzz_od.auto_battle.atomic_op.state_set import AtomicSetState
from zzz_od.auto_battle.atomic_op.wait import AtomicWait
from zzz_od.auto_battle.auto_battle_state import BattleStateEnum

if TYPE_CHECKING:
    from zzz_od.auto_battle.auto_battle_context import AutoBattleContext


class AtomicOpFactory:
    
    def __init__(self, auto_battle_context: AutoBattleContext):
        self.auto_battle_context = auto_battle_context

    def get_atomic_op(self, op_def: OperationDef) -> AtomicOp:
        """
        获取一个原子操作
        :return:
        """
        op_name = op_def.op_name
        op_data = op_def.data
        # 有几个特殊参数 在这里统一提取
        press: bool = op_name.endswith('-按下')
        release: bool = op_name.endswith('-松开')
        if press:
            press_time = float(op_data[0]) if (op_data is not None and len(op_data) > 0) else None
        else:
            press_time = None

        if op_name == AtomicBtnSwitchAgent.OP_NAME or op_name == '切换角色':
            # 切换角色 只是一个兼容 后续删掉
            return AtomicBtnSwitchAgent(self.auto_battle_context, op_def)
        elif op_name == AtomicBtnQuickAssist.OP_NAME:
            return AtomicBtnQuickAssist(self.auto_battle_context, op_def)
        elif op_name.startswith('按键') and not op_name.endswith('按下') and not op_name.endswith('松开'):
            return AtomicBtnCommon(self.auto_battle_context, op_def)
        elif op_name.startswith(BattleStateEnum.BTN_DODGE.value):
            return AtomicBtnDodge(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_SWITCH_NEXT.value):
            return AtomicBtnSwitchNext(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_SWITCH_PREV.value):
            return AtomicBtnSwitchPrev(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_SWITCH_NORMAL_ATTACK.value):
            return AtomicBtnNormalAttack(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_SWITCH_SPECIAL_ATTACK.value):
            return AtomicBtnSpecialAttack(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_ULTIMATE.value):
            return AtomicBtnUltimate(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_CHAIN_LEFT.value):
            return AtomicBtnChainLeft(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_CHAIN_RIGHT.value):
            return AtomicBtnChainRight(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_CHAIN_CANCEL.value):
            return AtomicBtnChainCancel(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_MOVE_W.value):
            return AtomicBtnMoveW(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_MOVE_S.value):
            return AtomicBtnMoveS(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_MOVE_A.value):
            return AtomicBtnMoveA(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_MOVE_D.value):
            return AtomicBtnMoveD(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name.startswith(BattleStateEnum.BTN_LOCK.value):
            return AtomicBtnLock(self.auto_battle_context, press=press, press_time=press_time, release=release)
        elif op_name == AtomicWait.OP_NAME:
            return AtomicWait(op_def)
        elif op_name == AtomicSetState.OP_NAME:
            return AtomicSetState(self.auto_battle_context.custom_context, op_def)
        elif op_name == AtomicClearState.OP_NAME:
            return AtomicClearState(self.auto_battle_context.custom_context, op_def)
        else:
            raise ValueError('非法的指令 %s' % op_name)