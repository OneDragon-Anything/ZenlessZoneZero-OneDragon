from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.goto.goto_menu import GotoMenu


class CityFundApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='city_fund',
            op_name=gt('丽都城募'),
            run_record=ctx.city_fund_record,
            need_notify=True,
        )

    @operation_node(name='打开菜单', is_start_node=True)
    def open_menu(self) -> OperationRoundResult:
        op = GotoMenu(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='打开菜单')
    @operation_node(name='点击丽都城募')
    def click_fund(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('菜单', '底部列表')
        return self.round_by_ocr_and_click(screen, '丽都城募', area=area,
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='点击丽都城募')
    @operation_node(name='点击成长任务')
    def click_task(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_and_click_area(screen, '丽都城募', '开启丽都城募')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '丽都城募', '按钮-已关闭-确认')
        if result.is_success:
            return self.round_success(status=result.status, wait=1)

        return self.round_by_find_and_click_area(screen, '丽都城募', '成长任务',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击成长任务')
    @operation_node(name='任务全部领取')
    def click_task_claim(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '丽都城募', '任务-全部领取',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='任务全部领取')
    @operation_node(name='点击等级回馈')
    def click_level(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '丽都城募', '等级回馈',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击等级回馈')
    @operation_node(name='等级全部领取')
    def click_level_claim(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '丽都城募', '等级-全部领取',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击成长任务', status='按钮-已关闭-确认')
    @node_from(from_name='等级全部领取')
    @node_from(from_name='等级全部领取', success=False)
    @operation_node(name='返回大世界')
    def back_to_world(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = CityFundApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()