from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent
from zzz_od.operation.zzz_operation import ZOperation


class OldCapital(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        在旧都失物的画面了 选择返回
        :param ctx:
        """
        event_name = HollowZeroSpecialEvent.OLD_CAPITAL.value.event_name
        ZOperation.__init__(
            self, ctx,
            op_name=gt(event_name, 'game')
        )

    @operation_node(name='选择', is_start_node=True)
    def choose_one(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '零号空洞-事件', '旧都失物-返回',
                                                 success_wait=1, retry_wait=1)
