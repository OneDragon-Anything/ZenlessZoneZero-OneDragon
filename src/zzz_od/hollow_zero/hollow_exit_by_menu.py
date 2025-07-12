from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class HollowExitByMenu(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        需要在空洞中 右下角有显示背包时使用
        如果有对话框的话会卡住
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name=gt('离开空洞', 'game')
        )

    @operation_node(name='点击菜单', is_start_node=True)
    def click_menu(self) -> OperationRoundResult:
        screen = self.screenshot()
        result = self.round_by_find_area(screen, '零号空洞-事件', '放弃')
        if result.is_success:  # 点击到出现了放弃按钮为止
            return self.round_success()

        result = self.round_by_click_area('零号空洞-事件', '菜单')
        if result.is_success:
            return self.round_wait(wait=1)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='点击菜单')
    @operation_node(name='点击离开')
    def click_leave(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '零号空洞-事件', '放弃',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击离开')
    @operation_node(name='确认离开')
    def confirm_leave(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '零号空洞-事件', '放弃-确认',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='确认离开')
    @operation_node(name='点击完成', node_max_retry_times=20)
    def click_finish(self) -> OperationRoundResult:
        screen = self.screenshot()

        # 这个按钮刚出现的时候可以按不到 需要重复按它
        result = self.round_by_find_and_click_area(screen, '零号空洞-事件', '通关-完成')
        if result.is_success:
            return self.round_wait(wait=1)

        result = self.round_by_find_area(screen, '零号空洞-入口', '街区')
        if result.is_success:  # 点击直到返回显示街区为止
            return self.round_success()

        return self.round_retry(wait=1)