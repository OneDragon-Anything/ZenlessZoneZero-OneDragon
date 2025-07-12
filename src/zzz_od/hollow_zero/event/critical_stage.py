from typing import List

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.event_ocr_result_handler import EventOcrResultHandler
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent
from zzz_od.hollow_zero.hollow_battle import HollowBattle
from zzz_od.operation.zzz_operation import ZOperation


class CriticalStage(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        确定出现事件后调用
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name=gt('关键进展', 'game')
        )

        self._handlers: List[EventOcrResultHandler] = [
            EventOcrResultHandler(HollowZeroSpecialEvent.CRITICAL_STAGE_ENTRY.value.event_name),
            EventOcrResultHandler(HollowZeroSpecialEvent.CRITICAL_STAGE_ENTRY_2.value.event_name),
        ]

    @operation_node(name='画面识别', is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        screen = self.screenshot()
        return hollow_event_utils.check_event_text_and_run(self, screen, self._handlers)

    @node_from(from_name='画面识别', status=HollowZeroSpecialEvent.CRITICAL_STAGE_ENTRY.value.event_name)
    @node_from(from_name='画面识别', status=HollowZeroSpecialEvent.CRITICAL_STAGE_ENTRY_2.value.event_name)
    @operation_node(name='自动战斗')
    def load_auto_op(self) -> OperationRoundResult:
        op = HollowBattle(self.ctx, is_critical_stage=True)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='自动战斗', status='普通战斗-完成')
    @operation_node(name='通关次数')
    def add_times(self) -> OperationRoundResult:
        self.ctx.hollow_zero_record.add_times()
        return self.round_success()
