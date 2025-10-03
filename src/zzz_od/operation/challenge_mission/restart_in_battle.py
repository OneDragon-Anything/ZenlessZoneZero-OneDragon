from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class RestartInBattle(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        在战斗画面 尝试退出
        :param ctx: 上下文
        """
        ZOperation.__init__(self, ctx, op_name=gt('战斗中-重新开始'))

    @operation_node(name='画面识别', is_start_node=True, node_max_retry_times=10)
    def check_screen(self) -> OperationRoundResult:
        # 点击直到出现 [退出战斗] 按钮
        result = self.round_by_find_area(self.last_screenshot, '战斗-菜单', '按钮-退出战斗')
        if result.is_success:
            return self.round_success(wait=1)  # 稍微等一下让按钮可按
        result = self.round_by_click_area('战斗画面', '菜单')
        return self.round_retry(result.status, wait=1)

    @node_from(from_name='画面识别')
    @operation_node(name='点击退出战斗')
    def click_exit_battle(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(self.last_screenshot, '战斗-菜单', '按钮-重新开始',
                                                 until_find_all=[('战斗-菜单', '按钮-退出战斗-确认')],
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击退出战斗')
    @operation_node(name='点击确认')
    def click_confirm(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='战斗-菜单', area_name='按钮-退出战斗-确认',
                                                 until_not_find_all=[('战斗-菜单', '按钮-退出战斗-确认')],
                                                 success_wait=1, retry_wait=1)

def __debug():
    """
    调试用
    """
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()

    op = RestartInBattle(ctx)
    op.execute()


if __name__ == "__main__":
    __debug()