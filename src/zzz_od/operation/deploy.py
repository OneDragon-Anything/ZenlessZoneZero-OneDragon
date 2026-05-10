from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
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
        return self.round_by_find_and_click_area(
            self.last_screenshot, '通用-出战', '按钮-出战',
            success_wait=1, retry_wait=1,
            until_not_find_all=[('通用-出战', '按钮-出战')]
        )

    @node_from(from_name='出战')
    @node_notify(when=NotifyTiming.CURRENT_FAIL, detail=True)
    @operation_node(name='出战确认')
    def check_level(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '通用-出战', '标题-驱动盘数量已达到可拥有上限')
        if result.is_success:
            return self.round_fail('驱动盘数量已达到可拥有上限')

        result = self.round_by_find_and_click_area(self.last_screenshot, '通用-出战', '按钮-队员数量少-确认')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        result = self.round_by_find_and_click_area(self.last_screenshot, '通用-出战', '按钮-等级低-确定并出战')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        if self.node_retry_times == self.node_max_retry_times - 1:
            # 这里返回成功, 从而不发送失败通知
            return self.round_success('无需确认', wait=1)
        return self.round_retry('无需确认', wait=1)


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.init_ocr()
    ctx.run_context.start_running()
    op = Deploy(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
