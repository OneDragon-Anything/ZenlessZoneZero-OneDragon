from typing import ClassVar

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_common import LostVoidChooseCommon
from zzz_od.application.notify.notify_app import NotifyApp
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidLottery(ZOperation):

    STATUS_NO_TIMES_LEFT: ClassVar[str] = '无剩余次数'
    STATUS_CONTINUE: ClassVar[str] = '继续抽奖'

    def __init__(self, ctx: ZContext):
        ZOperation.__init__(self, ctx, op_name='迷失之地-抽奖机')
        self._last_lottery_draw_count = 0  # 上次抽奖剩余次数, 用于判断抽奖次数是 1/1 还是 1/3

    @node_from(from_name='点击后确定', status=STATUS_CONTINUE)
    @operation_node(name='点击开始', is_start_node=True)
    def click_start(self) -> OperationRoundResult:
        # 识别剩余次数
        area = self.ctx.screen_loader.get_area('迷失之地-抽奖机', '文本-剩余次数')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)

        ocr_result_map = self.ctx.ocr.run_ocr(part)
        if len(ocr_result_map) == 0:
            return self.round_success(LostVoidLottery.STATUS_NO_TIMES_LEFT)

        is_valid = False
        lottery_draw_count = -1
        for ocr_result in ocr_result_map.keys():
            lottery_draw_count = str_utils.get_positive_digits(ocr_result, err=0)
            if lottery_draw_count > 0:
                is_valid = True
                break

        # 衰仔检测
        if self.ctx.lost_void.challenge_config.stop_when_found_lottery:
            # 疑似遇到了衰仔, 推送消息并停止运行
            if self._last_lottery_draw_count == 0 and lottery_draw_count == 1:
                log.info("疑似遇到了衰仔, 推送消息并停止脚本")
                interact_op = NotifyApp(self.ctx, "谁是衰仔?就在今天!")
                interact_op.execute()
                # 不管消息推送成不成功都需要停止脚本运行
                # stop_running() 会设置停止标志，脚本将在此函数返回之后结束运行
                self.ctx.run_context.stop_running()
            # 保存上一次的抽奖剩余次数, 避免叻仔的 1/3 误识别为衰仔
            if lottery_draw_count != -1:
                self._last_lottery_draw_count = lottery_draw_count

        if not is_valid:
            return self.round_success(LostVoidLottery.STATUS_NO_TIMES_LEFT)

        return self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-抽奖机', '按钮-开始',
                                                 success_wait=4, retry_wait=1)

    @node_from(from_name='点击开始')
    @operation_node(name='点击后确定')
    def confirm_after_click(self) -> OperationRoundResult:
        screen_name = self.check_and_update_current_screen(self.last_screenshot)
        interact_op = None

        if screen_name == '迷失之地-通用选择':
            interact_op = LostVoidChooseCommon(self.ctx)
        elif screen_name == '迷失之地-抽奖机':
            return self.round_success(LostVoidLottery.STATUS_CONTINUE)

        if interact_op is not None:
            op_result = interact_op.execute()
            if op_result.success:
                return self.round_wait(op_result.status, wait=1)
            else:
                return self.round_fail(op_result.status)

        result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-抽奖机', '按钮-获取确定')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        return self.round_retry('未能识别当前画面', wait=1)

    @node_from(from_name='点击开始', status=STATUS_NO_TIMES_LEFT)
    @node_from(from_name='点击后确定', success=False)
    @operation_node(name='返回大世界')
    def back_to_world(self) -> OperationRoundResult:
        in_world = self.ctx.lost_void.in_normal_world(self.last_screenshot)
        if not in_world:
            result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-抽奖机', '按钮-返回')
            return self.round_retry(result.status, wait=1)

        return self.round_success()



def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.lost_void.init_before_run()
    ctx.run_context.start_running()

    op = LostVoidLottery(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()