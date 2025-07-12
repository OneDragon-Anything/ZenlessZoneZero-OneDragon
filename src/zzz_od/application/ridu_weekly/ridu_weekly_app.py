from cv2.typing import MatLike

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.compendium.compendium_choose_tab import CompendiumChooseTab
from zzz_od.operation.compendium.open_compendium import OpenCompendium


class RiduWeeklyApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='ridu_weekly',
            op_name=gt('丽都周纪(领奖励)'),
            run_record=ctx.ridu_weekly_record,
            retry_in_od=True,  # 传送落地有可能会歪 重试
            need_notify=True,
        )

    @operation_node(name='快捷手册', is_start_node=True)
    def open_compendium(self) -> OperationRoundResult:
        op = OpenCompendium(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='快捷手册')
    @operation_node(name='日常')
    def choose_train(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name=f'快捷手册-日常')

    @node_from(from_name='日常')
    @operation_node(name='丽都周纪')
    def click_schedule(self) -> OperationRoundResult:
        screen = self.screenshot()

        return self.round_by_find_and_click_area(screen, '丽都周纪', '丽都周纪',
                                                 success_wait=2, retry_wait=1)

    @node_from(from_name='丽都周纪')
    @operation_node(name='领取积分')
    def claim_score(self, screen: MatLike = None) -> OperationRoundResult:
        if screen is None:
            screen = self.screenshot()

        for i in range(3):
            area = self.ctx.screen_loader.get_area('丽都周纪', f'积分行-{i+1}')

            result = self.round_by_ocr_and_click(screen, '100', area=area,
                                                 lcs_percent=1,
                                                 color_range=[(250, 250, 250), (255, 255, 255)])

            if result.is_success:
                return self.round_wait(result.status, wait=1)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='领取积分', success=False)  # 没有100积分之后
    @operation_node(name='领取奖励')
    def confirm_schedule(self) -> OperationRoundResult:
        return self.round_by_click_area('丽都周纪', '领取奖励',
                                        success_wait=1, retry_wait=1)

    @node_from(from_name='领取奖励')
    @operation_node(name='完成后返回')
    def finish(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = RiduWeeklyApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()