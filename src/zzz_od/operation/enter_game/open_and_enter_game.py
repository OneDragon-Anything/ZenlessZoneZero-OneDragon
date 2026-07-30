from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.open_game import OpenGame


class OpenAndEnterGame(Operation):

    def __init__(self, ctx: ZContext):
        self.ctx: ZContext = ctx
        Operation.__init__(self, ctx, op_name=gt('打开并登录游戏'),
                           need_check_game_win=False)

    @operation_node(name='打开游戏', is_start_node=True, screenshot_before_round=False)
    def open_game(self) -> OperationRoundResult:
        """打开游戏(禁用 HDR + 启动 exe + 等窗口就绪 + 恢复 HDR),委托 OpenGame。"""
        op = OpenGame(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='打开游戏')
    @node_notify(when=NotifyTiming.CURRENT_FAIL, detail=True)
    @operation_node(name='进入游戏')
    def enter_game(self) -> OperationRoundResult:
        from zzz_od.operation.enter_game.enter_game import EnterGame
        op = EnterGame(self.ctx)
        return self.round_by_op_result(op.execute())
