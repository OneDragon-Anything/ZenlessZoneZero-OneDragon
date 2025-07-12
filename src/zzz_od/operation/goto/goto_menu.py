from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.zzz_operation import ZOperation


class GotoMenu(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        需要保证在任何情况下调用，都能前往菜单
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name=gt('前往菜单'))

    @operation_node(name='画面识别', is_start_node=True, node_max_retry_times=60)
    def check_screen_and_run(self, screen: Optional[MatLike] = None) -> OperationRoundResult:
        if screen is None:
            screen = self.screenshot()

        result = self.round_by_goto_screen(screen=screen, screen_name='菜单', retry_wait=None)
        if result.is_success:
            return self.round_success(result.status)

        if (not result.is_fail  # fail是没有路径可以到达
                and self.ctx.screen_loader.current_screen_name is not None  # 能识别到当前画面 说明能打开菜单
        ):
            return self.round_wait(result.status, wait=1)

        # 到这里说明无法自动从当前画面前往菜单 就先统一返回大世界
        op = BackToNormalWorld(self.ctx)
        op_result = op.execute()
        if op_result.success:
            return self.round_retry(op_result.status, wait=1)
        else:
            # 大世界也没法返回的话 就不知道怎么去菜单了
            return self.round_fail(op_result.status)
