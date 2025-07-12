import time

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.transport import Transport
from zzz_od.operation.wait_normal_world import WaitNormalWorld
from zzz_od.operation.zzz_operation import ZOperation


class EatNoodle(ZOperation):

    def __init__(self, ctx: ZContext, noodle_name: str):
        """
        吃一碗拉面
        :param ctx:
        """
        ZOperation.__init__(self, ctx,
                            op_name='%s %s' % (gt('吃拉面'), gt(noodle_name, 'game'))
                            )
        self.noodle_name: str = noodle_name

    def handle_init(self):
        pass

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        op = Transport(self.ctx, '六分街', '拉面店')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='等待大世界加载')
    def wait_world(self) -> OperationRoundResult:
        op = WaitNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='等待大世界加载')
    @operation_node(name='移动交互')
    def move_and_interact(self) -> OperationRoundResult:
        self.ctx.controller.move_w(press=True, press_time=1, release=True)
        time.sleep(1)

        self.ctx.controller.interact(press=True, press_time=0.2, release=True)

        return self.round_success()

    @node_from(from_name='移动交互')
    @operation_node(name='等待拉面店加载', node_max_retry_times=10)
    def wait_noodle_shop(self) -> OperationRoundResult:
        screen = self.screenshot()
        # 画面加载的时候，是滑动出现的，返回按钮出现的时候，还未必能点击选中商品，因此要success_wait
        return self.round_by_find_area(screen, '菜单', '返回',
                                       success_wait=1, retry_wait=1)

    @node_from(from_name='等待拉面店加载')
    @operation_node(name='选择拉面')
    def choose_noodle(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('拉面店', '拉面列表')

        result = self.round_by_ocr_and_click(screen, self.noodle_name, area=area)
        if result.is_success:
            return self.round_success(result.status, wait=1)

        start_point = area.center
        end_point = start_point + Point(-100, 0)
        self.ctx.controller.drag_to(start=start_point, end=end_point)
        return self.round_retry(result.status, wait=0.5)

    @node_from(from_name='选择拉面')
    @operation_node(name='点单')
    def click_order(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '拉面店', '点单',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点单')
    @operation_node(name='点单后确认')
    def confirm_after_order(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '拉面店', '点单确认',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点单后确认')
    @operation_node(name='点单后跳过')
    def skip_after_order(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '拉面店', '效果确认')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        # 这个点击很怪 需要多点几次 直到出现效果确认
        result = self.round_by_find_and_click_area(screen, '咖啡店', '点单后跳过')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='点单后跳过')
    @operation_node(name='效果确认')
    def effect_after_order(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '拉面店', '效果确认',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='效果确认')
    @operation_node(name='返回大世界')
    def back_to_normal_world(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())
