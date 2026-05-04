from collections.abc import Callable

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame


class ZOperation(Operation):
    def __init__(
        self,
        ctx: ZContext,
        node_max_retry_times: int = 3,
        op_name: str = "",
        timeout_seconds: float = -1,
        op_callback: Callable[[OperationResult], None] | None = None,
        need_check_game_win: bool = True,
    ):
        self.ctx: ZContext = ctx
        op_to_enter_game = OpenAndEnterGame(ctx)
        Operation.__init__(
            self,
            ctx=ctx,
            node_max_retry_times=node_max_retry_times,
            op_name=op_name,
            timeout_seconds=timeout_seconds,
            op_callback=op_callback,
            need_check_game_win=need_check_game_win,
            op_to_enter_game=op_to_enter_game,
        )

    def check_game_initialized(self) -> OperationRoundResult:
        """检查游戏是否完成初始化，若为云游戏模式则执行排队逻辑。

        Returns:
            OperationRoundResult: 如果游戏完成初始化则成功，否则失败。
        """
        # 如果是云游戏 那么先阻塞运行CloudGameQueue
        if self.ctx.game_account_config.is_cloud_game:
            from zzz_od.application.cloud_queue.cloud_queue import CloudGameQueue

            cloud_queue_op = CloudGameQueue(self.ctx)
            return self.round_by_op_result(cloud_queue_op.execute())

        # 对于非云游戏模式，直接返回成功
        return self.round_success()
