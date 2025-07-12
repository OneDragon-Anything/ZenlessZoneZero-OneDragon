from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent
from zzz_od.operation.zzz_operation import ZOperation


class HollowInteract(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        确定出现事件后调用
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name=gt(HollowZeroSpecialEvent.NEED_INTERACT.value.event_name, 'game')
        )

    @operation_node(name='交互', is_start_node=True)
    def interact(self) -> OperationRoundResult:
        self.ctx.controller.interact(press=True, press_time=0.2, release=True)

        return self.round_success(wait=1)
