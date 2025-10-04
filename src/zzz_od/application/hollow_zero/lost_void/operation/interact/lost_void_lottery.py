from typing import ClassVar

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_common import LostVoidChooseCommon
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidLottery(ZOperation):

    STATUS_NO_TIMES_LEFT: ClassVar[str] = '无剩余次数'
    STATUS_CONTINUE: ClassVar[str] = '继续抽奖'

    def __init__(self, ctx: ZContext):
        ZOperation.__init__(self, ctx, op_name='迷失之地-抽奖机')

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
        for ocr_result in ocr_result_map.keys():
            digit = str_utils.get_positive_digits(ocr_result, err=0)
            if digit > 0:
                is_valid = True
                break

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