from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.operation.zzz_operation import ZOperation


class LeaveRandomZone(ZOperation):

    def __init__(self, ctx: ZContext):
        ZOperation.__init__(
            self, ctx,
            op_name=gt('不宜久留', 'game')
        )

    @operation_node(name='画面识别', is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        screen = self.screenshot()

        event = hollow_event_utils.check_screen(self.ctx, screen, set())
        if event == '特殊区域':
            return self.round_success(event)

        result = self.round_by_find_area(screen, '零号空洞-事件', '交互可再次触发事件')
        if result.is_success:
            self.ctx.controller.interact(press=True, press_time=0.2, release=True)

            return self.round_wait(result.status, wait=1)

        return self.round_retry(result.status, wait=1)

