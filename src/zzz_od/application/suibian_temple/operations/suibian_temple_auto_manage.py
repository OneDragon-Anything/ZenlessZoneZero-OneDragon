from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class SuibianTempleAutoManage(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        随便观 - 自动托管

        需要在随便观主界面时候调用，完成后返回随便观主界面

        Args:
            ctx: 上下文
        """
        ZOperation.__init__(self, ctx,
                            op_name=f'{gt("随便观", "game")} {gt("自动托管", "game")}')


    @operation_node(name='点击经营方针', is_start_node=True)
    def click_business_policy(self) -> OperationRoundResult:
        result1 = self.round_by_ocr_and_click(self.last_screenshot, '经营方针')
        if result1.is_success:
            return self.round_success(status=result1.status, wait=1)

        result = self.round_by_ocr(self.last_screenshot, '自动托管中')
        if result.is_success:
            return self.round_success(status=result.status, wait=1)

        return self.round_retry(status=result1.status, wait=1)

    @node_from(from_name='点击经营方针')
    @operation_node(name='点击开始')
    def click_start(self) -> OperationRoundResult:
        return self.round_by_ocr_and_click(self.last_screenshot, '开始托管',
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='点击经营方针', status='自动托管中')
    @node_from(from_name='点击开始')
    @operation_node(name='返回随便观')
    def back_to_entry(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(self.last_screenshot, screen_name_list=['随便观-入口'])
        if current_screen_name is not None:
            return self.round_success()

        target_cn_list = [
            '确认'
        ]
        result = self.round_by_ocr_and_click_by_priority(target_cn_list)
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '返回')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)
        else:
            return self.round_retry(status=result.status, wait=1)


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    ctx.run_context.current_instance_idx = ctx.current_instance_idx
    ctx.run_context.current_app_id = 'suibian_temple'
    ctx.run_context.current_group_id = 'one_dragon'

    op = SuibianTempleAutoManage(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()