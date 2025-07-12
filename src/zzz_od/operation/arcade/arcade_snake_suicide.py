from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.arcade.arcade_start_game import ArcadeStartGame
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.zzz_operation import ZOperation


class ArcadeSnakeSuicide(ZOperation):

    def __init__(self, ctx: ZContext, total_cnt: int):
        """
        蛇对蛇中自杀 用于完成每周行程
        完成指定次数后 返回大世界
        :param ctx:
        """
        ZOperation.__init__(self, ctx,
                            op_name=gt('蛇对蛇自杀')
                            )
        self.total_cnt: int = total_cnt  # 所需的次数
        self.finish_cnt: int = 0  # 完成次数


    def handle_init(self):
        self.finish_cnt: int = 0  # 完成次数

    @operation_node(name='进入游戏')
    def start_game(self) -> OperationRoundResult:
        op = ArcadeStartGame(self.ctx, '蛇对蛇')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='进入游戏')
    @node_from(from_name='点击空白处继续', status='蛇对蛇-点击空白处继续')
    @operation_node(name='等待加载', node_max_retry_times=20)
    def wait_game_load(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_area(screen, '电玩店', '蛇对蛇-加载完成', retry_wait=1)

    @node_from(from_name='等待加载')
    @operation_node(name='点击空白处继续', node_max_retry_times=20)
    def click_empty(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '电玩店', '蛇对蛇-点击空白处继续')
        if result.is_success:
            self.finish_cnt += 1
            if self.finish_cnt >= self.total_cnt:
                return self.round_success()
            else:
                return self.round_by_find_and_click_area(screen, '电玩店', '蛇对蛇-点击空白处继续',
                                                         success_wait=3, retry_wait=1)

        self.ctx.controller.keyboard_controller.press('w', press_time=0.2)
        return self.round_retry(result.status, wait=1)

    @node_from(from_name='点击空白处继续')
    @operation_node(name='返回大世界')
    def back_to_normal_world(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

