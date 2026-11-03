from collections.abc import Callable

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResult
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

    def wait_loading_end(self, wait: float = 2) -> OperationRoundResult | None:
        """
        通用方法：判断当前画面是否还在加载界面（识别「加载中」画面的 NOW LOADING 文本）。
        供加载过渡后的节点调用，减轻每个节点自己识别加载画面的负担。

        :param wait: 仍在加载时的等待秒数
        :return: 仍在加载时返回等待轮结果（节点可直接 return）；加载已结束返回 None，
            调用方继续自己的识别逻辑
        """
        result = self.round_by_find_area(self.last_screenshot, '加载中', '加载中')
        if result.is_success:
            return self.round_wait(result.status, wait=wait)
        return None
