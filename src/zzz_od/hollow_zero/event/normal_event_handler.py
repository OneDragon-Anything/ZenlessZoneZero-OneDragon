from typing import List

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.event_ocr_result_handler import EventOcrResultHandler
from zzz_od.hollow_zero.game_data.hollow_zero_event import HallowZeroEvent
from zzz_od.operation.zzz_operation import ZOperation


class NormalEventHandler(ZOperation):

    def __init__(self, ctx: ZContext, event: HallowZeroEvent):
        """
        确定出现事件后调用
        :param ctx:
        """
        event_name = event.event_name
        ZOperation.__init__(
            self, ctx,
            op_name=gt(event_name, 'game')
        )

        self._handlers: List[EventOcrResultHandler] = []

        for opt in event.options:
            self._handlers.append(EventOcrResultHandler(
                target_cn=opt.ocr_word,
                status=opt.option_name,
                click_wait=opt.wait,
                lcs_percent=opt.lcs_percent
            ))
        self._handlers.append(
            EventOcrResultHandler(event_name, is_event_mark=True)
        )

    @operation_node(name='画面识别', is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        screen = self.screenshot()  # TODO 顺便识别是否同一个事件 不是的话就可以退出
        return hollow_event_utils.check_event_text_and_run(self, screen, self._handlers)


def __debug_opts():
    """
    识别图片输出选项
    :return:
    """
    from zzz_od.context.zzz_context import ZContext
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    from zzz_od.hollow_zero.hollow_runner import HollowRunner
    op = HollowRunner(ctx)
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('hz_1')
    # from one_dragon.utils import os_utils
    # import os
    # from one_dragon.utils import cv2_utils
    # screen = cv2_utils.read_image(
    #     os.path.join(os_utils.get_path_under_work_dir('.debug', 'devtools', 'screen', 'hollow_zero_friend'),
    #                  'qingyi_1.png')
    # )
    event_name = hollow_event_utils.check_screen(op.ctx, screen, set())
    print(event_name)
    e = ctx.hollow.data_service.get_normal_event_by_name(event_name)
    op2 = NormalEventHandler(ctx, e)
    hollow_event_utils.check_event_text_and_run(op, screen, op2._handlers)


if __name__ == '__main__':
    __debug_opts()
