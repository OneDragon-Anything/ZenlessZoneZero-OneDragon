import time

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cal_utils
from zzz_od.operation.turning.turn_compensation import AngleTurnCompensator


def turn_to_angle_and_interact(
    operation: Operation,
    compensator: AngleTurnCompensator,
    target_angle: float,
    turn_status: str,
    angle_threshold: float = 2.0,
    turn_wait: float = 0.5,
    move_time: float = 1,
    post_move_wait: float = 1,
    interact_time: float = 0.2,
) -> OperationRoundResult:
    """转向目标角度，前移后交互。"""
    mini_map = operation.ctx.world_patrol_service.cut_mini_map(operation.last_screenshot)
    if not mini_map.play_mask_found:
        return operation.round_retry(status='未识别到小地图', wait=1)

    current_angle = mini_map.view_angle
    if current_angle is None:
        return operation.round_retry(status='识别朝向失败', wait=1)

    angle_diff = cal_utils.angle_delta(current_angle, target_angle)
    if abs(angle_diff) > angle_threshold:
        compensator.turn_from_angle(current_angle, angle_diff)
        return operation.round_retry(status=turn_status, wait=turn_wait)

    operation.ctx.controller.move_w(press=True, press_time=move_time, release=True)
    time.sleep(post_move_wait)

    operation.ctx.controller.interact(press=True, press_time=interact_time, release=True)

    return operation.round_success()
