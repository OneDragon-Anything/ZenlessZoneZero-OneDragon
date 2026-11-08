from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.event import hollow_event_utils
from zzz_od.hollow_zero.event.event_ocr_result_handler import EventOcrResultHandler
from zzz_od.hollow_zero.game_data.hollow_zero_event import (
    HallowZeroEvent,
    HallowZeroNormalEventOption,
)
from zzz_od.operation.zzz_operation import ZOperation

_HP_LOSS_WORDS: tuple[str, ...] = ('损失', '消耗全队', '失去', '降低至', '变为')
_LEAVE_WORDS: tuple[str, ...] = ('离开', '不需要', '拒绝')  # 表示不拿收益直接结束的选项


def is_hp_loss_option(option: HallowZeroNormalEventOption) -> bool:
    """
    选项是否会扣血 通过选项名称和描述中的文字判断
    """
    text = f'{option.option_name}{option.desc or ""}'
    return '生命' in text and any(word in text for word in _HP_LOSS_WORDS)


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

        self._handlers: list[EventOcrResultHandler] = []

        # 零号业绩速刷模式 不拿事件收益 有离开的选项就只选离开 否则也不选会扣血的选项
        skip_hp_loss: bool = self.ctx.withered_domain.force_only_boss
        options: list[HallowZeroNormalEventOption] = event.options
        if skip_hp_loss:
            leave_options = [
                opt for opt in options
                if any(word in opt.option_name for word in _LEAVE_WORDS)
            ]
            if len(leave_options) > 0:
                options = leave_options
            else:
                options = [opt for opt in options if not is_hp_loss_option(opt)]

        for opt in options:
            self._handlers.append(EventOcrResultHandler(
                target_cn=opt.ocr_word,
                status=opt.option_name,
                click_wait=opt.wait,
                lcs_percent=opt.lcs_percent
            ))
        if skip_hp_loss:
            # 没有其他可选的选项时 选择离开
            self._handlers.append(EventOcrResultHandler(target_cn='离开'))
        self._handlers.append(
            EventOcrResultHandler(event_name, is_event_mark=True)
        )

    @operation_node(name='画面识别', is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        return hollow_event_utils.check_event_text_and_run(
            self, self.last_screenshot, self._handlers,
            force_bottom_fallback=self.ctx.withered_domain.force_only_boss,
        )


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
    e = ctx.withered_domain.data_service.get_normal_event_by_name(event_name)
    op2 = NormalEventHandler(ctx, e)
    hollow_event_utils.check_event_text_and_run(op, screen, op2._handlers)


if __name__ == '__main__':
    __debug_opts()
