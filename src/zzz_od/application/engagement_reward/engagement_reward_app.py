from typing import ClassVar

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from zzz_od.application.engagement_reward import engagement_reward_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class EngagementRewardApp(ZApplication):

    STATUS_NO_REWARD: ClassVar[str] = '无奖励可领取'
    STATUS_CLAIM_SUCCESS: ClassVar[str] = '日常奖励领取成功'

    def __init__(self, ctx: ZContext):
        """
        领取活跃度奖励
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=engagement_reward_const.APP_ID,
            op_name=engagement_reward_const.APP_NAME,
        )

    @operation_node(name='返回大世界', is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='返回大世界')
    @operation_node(name='快捷手册-日常')
    def goto_compendium_daily(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='快捷手册-日常')

    @node_from(from_name='快捷手册-日常')
    @operation_node(name='点击奖励')
    def click_reward(self) -> OperationRoundResult:
        return self.round_by_click_area('快捷手册', '活跃度奖励-4', success_wait=1, retry_wait=1)

    @node_from(from_name='点击奖励')
    @operation_node(name='查看奖励结果')
    def check_reward(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(self.last_screenshot, '快捷手册', '活跃度奖励-确认', success_wait=1, retry_wait=1)
        if result.is_success:
            return self.round_success('日常奖励领取成功')

        result = self.round_by_find_area(self.last_screenshot, '快捷手册', '活跃度奖励-奖励预览')
        if result.is_success:
            result = self.round_by_click_area('快捷手册', '活跃度奖励-4', success_wait=1, retry_wait=1)
            if result.is_success:
                return self.round_success('日常奖励已领取或活跃度未满')

        return self.round_success('未找到确认按钮或奖励预览')

    @node_from(from_name='查看奖励结果')
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='识别活跃度')
    def check_engagement(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('快捷手册', '今日最大活跃度')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)

        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        num = str_utils.get_positive_digits(ocr_result, None)
        if num is None:
            return self.round_retry('识别活跃度失败', wait_round_time=1)

        return self.round_success('活跃度已满') if '4' in str(num) else self.round_fail(f'活跃度未满，当前{num}')

    @node_from(from_name='识别活跃度')
    @operation_node(name='完成后返回大世界')
    def back_afterwards(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        op.execute()
        return self.round_success() if self.previous_node.is_success else self.round_fail()


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    op = EngagementRewardApp(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
