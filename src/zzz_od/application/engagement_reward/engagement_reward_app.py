from typing import ClassVar

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.compendium.compendium_choose_tab import CompendiumChooseTab
from zzz_od.operation.compendium.open_compendium import OpenCompendium


class EngagementRewardApp(ZApplication):

    STATUS_NO_REWARD: ClassVar[str] = '无奖励可领取'

    def __init__(self, ctx: ZContext):
        """
        每天自动接收邮件奖励
        """
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='engagement_reward',
            op_name=gt('活跃度奖励'),
            run_record=ctx.engagement_reward_run_record,
            need_notify=True,
        )

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        self.idx: int = 4

    @operation_node(name='快捷手册-日常', is_start_node=True)
    def goto_compendium_daily(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='快捷手册-日常')

    @node_from(from_name='快捷手册-日常')
    @operation_node(name='识别活跃度')
    def check_engagement(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('快捷手册', '今日最大活跃度')
        part = cv2_utils.crop_image_only(screen, area.rect)

        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        num = str_utils.get_positive_digits(ocr_result, None)
        if num is None:
            return self.round_retry('识别活跃度失败', wait_round_time=1)

        self.idx = 4  # 只需要点最后一个就可以领取

        return self.round_success()

    @node_from(from_name='识别活跃度')
    @operation_node(name='点击奖励')
    def click_reward(self) -> OperationRoundResult:
        if self.idx > 1:
            area_name = ('活跃度奖励-%d' % self.idx)
            return self.round_by_click_area('快捷手册', area_name, success_wait=1, retry_wait=1)
        else:
            return self.round_fail(EngagementRewardApp.STATUS_NO_REWARD)

    @node_from(from_name='点击奖励')
    @operation_node(name='查看奖励结果')
    def check_reward(self) -> OperationRoundResult:
        screen = self.screenshot()
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        return self.round_by_find_and_click_area(screen, '快捷手册', '活跃度奖励-确认', success_wait=1, retry_wait=1)

    @node_from(from_name='查看奖励结果', success=False)
    @node_from(from_name='识别活跃度', status=STATUS_NO_REWARD)
    @operation_node(name='完成后返回大世界')
    def back_afterwards(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.start_running()
    op = EngagementRewardApp(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
