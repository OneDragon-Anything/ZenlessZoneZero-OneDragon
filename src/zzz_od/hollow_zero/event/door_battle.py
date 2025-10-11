from typing import List

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.event_ocr_result_handler import EventOcrResultHandler
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent
from zzz_od.operation.zzz_operation import ZOperation


class DoorBattle(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        确定出现事件后调用
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name='门扉禁闭-善战'
        )

        self._handlers: List[EventOcrResultHandler] = [
            EventOcrResultHandler(HollowZeroSpecialEvent.DOOR_BATTLE_ENTRY.value.event_name, click_wait=3),
        ]

        for e in self.ctx.withered_domain.data_service.normal_events:
            if e.entry_name == '门扉禁闭-侵蚀':  # 兼容识别错误的情况
                for opt in e.options:
                    self._handlers.append(EventOcrResultHandler(opt.option_name))

    @operation_node(name='画面识别', is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        return hollow_event_utils.check_event_text_and_run(self, self.last_screenshot, self._handlers)