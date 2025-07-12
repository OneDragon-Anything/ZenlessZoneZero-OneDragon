import time

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.transport import Transport
from zzz_od.operation.wait_normal_world import WaitNormalWorld
from zzz_od.operation.zzz_operation import ZOperation


class ArcadeStartGame(ZOperation):

    def __init__(self, ctx: ZContext, game_name: str):
        """
        电玩店里开始一局游戏
        :param ctx:
        """
        ZOperation.__init__(self, ctx,
                            op_name='%s %s' % (gt('开始街机游戏'), gt(game_name, 'game'))
                            )
        self.game_name: str = game_name  # 游戏名称


    def handle_init(self):
        pass

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        op = Transport(self.ctx, '六分街', '电玩店')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='等待大世界加载')
    def wait_world(self) -> OperationRoundResult:
        op = WaitNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='等待大世界加载')
    @operation_node(name='移动交互')
    def move_and_interact(self) -> OperationRoundResult:
        self.ctx.controller.move_w(press=True, press_time=1.5, release=True)
        time.sleep(1)

        self.ctx.controller.interact(press=True, press_time=0.2, release=True)

        return self.round_success()

    @node_from(from_name='移动交互')
    @operation_node(name='等待加载', node_max_retry_times=10)
    def wait_noodle_shop(self) -> OperationRoundResult:
        screen = self.screenshot()
        # 画面加载的时候，是滑动出现的，返回按钮出现的时候，还未必能点击选中商品，因此要success_wait
        return self.round_by_find_area(screen, '菜单', '返回',
                                       success_wait=1, retry_wait=1)

    @node_from(from_name='等待加载')
    @operation_node(name='选择模式')
    def choose_mode(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('电玩店', '模式列表')
        return self.round_by_ocr_and_click(screen, '街机模式', area=area,
                                           success_wait=3, retry_wait=1)


    @node_from(from_name='选择模式')
    @operation_node(name='选择游戏')
    def choose_game(self) -> OperationRoundResult:
        screen = self.screenshot()

        area1 = self.ctx.screen_loader.get_area('电玩店', '游戏名称')
        result1 = self.round_by_ocr(screen, self.game_name, area=area1)

        if result1.is_success:
            return self.round_success(result1.status)

        self.round_by_click_area('电玩店', '下一个游戏')
        return self.round_retry(result1.status, wait=1)

    @node_from(from_name='选择游戏')
    @operation_node(name='点击选择')
    def click_choose(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '电玩店', '选择',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击选择')
    @operation_node(name='点击开始游戏')
    def click_start(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '电玩店', '开始游戏',
                                                 success_wait=1, retry_wait=1)
