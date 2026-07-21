"""通用 normal 战斗 op(覆盖 NotoriousHunt/ExpertChallenge/CombatSimulation/AreaPatrol 类朴素战斗)。

纯继承 BattleOpBase 节点图,只覆写 _get_auto_battle_op_name。经 run_operation 跑。
"""
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.battle.base import BattleOpBase


class NormalBattleOp(BattleOpBase):
    """通用 normal 战斗 op。

    纯继承基类节点图(加载 → 等画面 → 战前移动 → 开始战斗 → 自动战斗 → 战斗结束),
    不重定义/不 shadow 任何节点;只覆写 _get_auto_battle_op_name。
    """

    def __init__(self, ctx: ZContext, auto_battle_config: str = '全配队通用', predefined_team_idx: int = -1) -> None:
        """默认 op_name='普通战斗'。"""
        BattleOpBase.__init__(self, ctx, op_name='普通战斗',
                              auto_battle_config=auto_battle_config, predefined_team_idx=predefined_team_idx)

    def _get_auto_battle_op_name(self) -> str | None:
        """predefined_team_idx==-1 → auto_battle_config;否则 team_list[idx].auto_battle。"""
        if self.predefined_team_idx == -1:
            return self.auto_battle_config
        return self.ctx.team_config.team_list[self.predefined_team_idx].auto_battle
