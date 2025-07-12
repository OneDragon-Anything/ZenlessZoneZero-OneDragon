from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class Deploy(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        在出战页面 点击出战
        同时处理可能出现的对话框
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name=gt('出战', 'game'))

    @operation_node(name='出战', is_start_node=True)
    def deploy(self) -> OperationRoundResult:
        screen = self.screenshot()

        return self.round_by_find_and_click_area(
            screen, '通用-出战', '按钮-出战',
            success_wait=1, retry_wait=1,
            until_not_find_all=[('通用-出战', '按钮-出战')]
        )

    @node_from(from_name='出战')
    @operation_node(name='出战确认')
    def check_level(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_and_click_area(screen, '通用-出战', '按钮-队员数量少-确认')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '通用-出战', '按钮-等级低-确定并出战')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        return self.round_retry('无需确认', wait=1)

    @node_from(from_name='出战确认')
    @node_from(from_name='出战确认', success=False)
    @operation_node(name='进入成功')
    def finish(self) -> OperationRoundResult:
        return self.round_success()


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.start_running()
    op = Deploy(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()