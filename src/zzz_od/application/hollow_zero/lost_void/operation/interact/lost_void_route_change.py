from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidRouteChange(ZOperation):

    def __init__(self, ctx: ZContext):
        ZOperation.__init__(self, ctx, op_name='迷失之地-路径迭换')

    @operation_node(name='返回', is_start_node=True, node_max_retry_times=5)
    def back_to_world(self) -> OperationRoundResult:
        screen = self.screenshot()

        in_world = self.ctx.lost_void.in_normal_world(screen)
        if not in_world:
            result = self.round_by_find_and_click_area(screen, '迷失之地-路径迭换', '按钮-返回')
            return self.round_retry(result.status, wait=1)

        return self.round_success()
