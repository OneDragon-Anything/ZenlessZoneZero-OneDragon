from typing import Optional

from one_dragon.base.conditional_operation.conditional_operator import ConditionalOperator
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.operation.operation_node import OperationNode
from one_dragon.utils.i18_utils import gt
from zzz_od.application.zzz_application import ZApplication
from zzz_od.auto_battle.auto_battle_state import BattleStateEnum
from zzz_od.context.zzz_context import ZContext


class LogTestApp(ZApplication):

    def __init__(self, ctx: ZContext):
        """
        识别后进行闪避
        """
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='log_test',
            op_name=gt('日志输入测试'),
            check_game_win=False
        )

        self.auto_op: Optional[ConditionalOperator] = None

    def add_edges_and_nodes(self) -> None:
        """
        初始化前 添加边和节点 由子类实行
        :return:
        """
        log = OperationNode('打印日志', self.log)
        self.param_start_node = log

    def log(self) -> OperationRoundResult:
        self.ctx.dispatch_event(BattleStateEnum.BTN_MOVE_W.value)
        self.ctx.dispatch_event(BattleStateEnum.BTN_MOVE_S.value)
        self.ctx.dispatch_event(BattleStateEnum.BTN_MOVE_A.value)
        self.ctx.dispatch_event(BattleStateEnum.BTN_MOVE_D.value)
        return self.round_wait(wait_round_time=0.001)
