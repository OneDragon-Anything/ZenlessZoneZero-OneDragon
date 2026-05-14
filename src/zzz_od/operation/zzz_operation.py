from collections.abc import Callable

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame


class ZOperation(Operation):

    def __init__(self, ctx: ZContext,
                 node_max_retry_times: int = 3,
                 op_name: str = '',
                 timeout_seconds: float = -1,
                 op_callback: Callable[[OperationResult], None] | None = None,
                 need_check_game_win: bool = True
                 ):
        self.ctx: ZContext = ctx
        op_to_enter_game = OpenAndEnterGame(ctx)
        Operation.__init__(self,
                           ctx=ctx,
                           node_max_retry_times=node_max_retry_times,
                           op_name=op_name,
                           timeout_seconds=timeout_seconds,
                           op_callback=op_callback,
                           need_check_game_win=need_check_game_win,
                           op_to_enter_game=op_to_enter_game)
