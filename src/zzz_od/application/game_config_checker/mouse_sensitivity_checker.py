import time

import numpy as np

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.transport import Transport


class MouseSensitivityChecker(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id='mouse_sensitivity_checker',
            op_name=gt('鼠标灵敏度检测'),
        )

        self.turn_distance: int = 500  # 转向时鼠标移动的距离
        self.angle_check_times: int = 0
        self.last_angle: float = 0
        self.angle_diff_list: list[float] = []

    @operation_node(name='返回大世界')
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='返回大世界')
    @operation_node(name='传送')
    def transport(self) -> OperationRoundResult:
        op = Transport(self.ctx, '录像店', '房间')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='转向检测', is_start_node=False)
    def check(self) -> OperationRoundResult:
        mini_map = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)
        angle = mini_map.view_angle

        if angle is None:
            return self.round_fail(status='识别朝向失败')
        log.info(f'当前识别朝向 {angle:.2f}')

        if self.angle_check_times > 0:
            angle_diff = angle - self.last_angle
            if angle_diff > 180:
                angle_diff -= 360
            log.info(f'本次角度偏移 {angle_diff:.2f}')
            self.angle_diff_list.append(angle_diff)

        self.angle_check_times += 1
        if self.angle_check_times >= 10:
            return self.round_success()

        self.last_angle = angle
        self.ctx.controller.turn_by_distance(self.turn_distance)
        return self.round_wait(status='转向继续下一轮识别', wait=2)

    @node_from(from_name='转向检测')
    @operation_node(name='结果统计')
    def calculate(self) -> OperationRoundResult:
        dx = self.turn_distance / float(np.mean(self.angle_diff_list))
        self.ctx.game_config.turn_dx = dx
        self.ctx.controller.turn_dx = self.ctx.game_config.turn_dx
        log.info(f'转向系数={dx:0.6f}')
        return self.round_success('完成检测')


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = MouseSensitivityChecker(ctx)
    app.execute()


def __debug_turn_dx():
    ctx = ZContext()
    ctx.init_by_config()
    for _ in range(10):
        _, screen = ctx.controller.screenshot()
        mini_map = ctx.world_patrol_service.cut_mini_map(screen)
        angle = mini_map.view_angle
        print(angle)
        ctx.controller.turn_by_angle_diff(45)
        time.sleep(2)


if __name__ == '__main__':
    # __debug()
    __debug_turn_dx()