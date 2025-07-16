from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class ChooseNextOrFinishAfterBattle(ZOperation):

    def __init__(self, ctx: ZContext, try_next: bool):
        """
        在战斗结束画面 尝试点击 【再来一次】 或者 【结束】
        :param ctx: 上下文
        :param try_next: 是否尝试点击下一次
        """
        ZOperation.__init__(self, ctx, op_name=gt('战斗后选择'))
        self.try_next: bool = try_next

    @operation_node(name='判断再来一次', is_start_node=True)
    def check_next(self) -> OperationRoundResult:
        screen = self.screenshot()
        if self.try_next:
            return self.round_by_find_and_click_area(screen, '战斗画面', '战斗结果-再来一次',
                                                     success_wait=1, retry_wait=1)
        else:
            return self.round_by_find_and_click_area(screen, '战斗画面', '战斗结果-完成',
                                                     success_wait=5, retry_wait=1)

    @node_from(from_name='判断再来一次', success=False)
    @operation_node(name='无再来一次')
    def finish(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '战斗画面', '战斗结果-完成',
                                                 success_wait=5, retry_wait=1)

