import time

import numpy as np

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from zzz_od.application.game_config_checker.mouse_sensitivity_checker import (
    mouse_sensitivity_checker_const,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.transport import Transport


class MouseSensitivityChecker(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=mouse_sensitivity_checker_const.APP_ID,
            op_name=mouse_sensitivity_checker_const.APP_NAME,
        )

        self.turn_distance: int = 500  # 鼠标模式：转向时鼠标移动的距离
        self.gamepad_test_duration: float = 0.3  # 手柄模式：右摇杆推动时长（秒）
        self.angle_check_times: int = 0
        self.last_angle: float = 0
        self.angle_diff_list: list[float] = []

    @property
    def _is_gamepad_mode(self) -> bool:
        return self.ctx.controller.background_mode

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
        if self._is_gamepad_mode and self.ctx.game_config.turn_dx == 0:
            return self.round_fail(status='手柄灵敏度检测需先完成鼠标灵敏度检测 (turn_dx)')

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

        if self._is_gamepad_mode:
            self._gamepad_turn_test()
        else:
            self.ctx.controller.turn_by_distance(self.turn_distance)

        return self.round_wait(status='转向继续下一轮识别', wait=2)

    def _gamepad_turn_test(self) -> None:
        """直接推右摇杆固定时长，用于校准 gamepad_turn_speed。"""
        pad = self.ctx.controller.btn_controller.pad
        pad.right_joystick_float(1.0, 0)  # 满偏转向右
        pad.update()
        time.sleep(self.gamepad_test_duration)
        pad.right_joystick_float(0, 0)
        pad.update()

    @node_from(from_name='转向检测')
    @operation_node(name='结果统计')
    def calculate(self) -> OperationRoundResult:
        mean_diff = float(np.mean(self.angle_diff_list))

        if abs(mean_diff) < 1e-6:
            return self.round_fail(status='平均角度差过小，检测结果不可靠')

        if self._is_gamepad_mode:
            # gamepad_turn_speed = |turn_dx| * |mean_angle_diff| / test_duration
            turn_dx = self.ctx.game_config.turn_dx
            speed = abs(turn_dx * mean_diff) / self.gamepad_test_duration
            self.ctx.game_config.gamepad_turn_speed = speed
            self.ctx.controller.gamepad_turn_speed = speed
            log.info(f'手柄转速 gamepad_turn_speed={speed:.2f} (turn_dx={turn_dx:.4f}, '
                     f'平均角度差={mean_diff:.2f}°, 测试时长={self.gamepad_test_duration}s)')
        else:
            dx = self.turn_distance / mean_diff
            self.ctx.game_config.turn_dx = dx
            self.ctx.controller.turn_dx = dx
            log.info(f'转向系数 turn_dx={dx:.6f}')

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
