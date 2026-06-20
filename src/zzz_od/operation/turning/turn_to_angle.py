from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cal_utils


def turn_to_angle(
    operation: Operation,
    target_angle: float,
    turn_status: str,
    angle_threshold: float = 2.0,
    turn_wait: float = 0.5,
) -> OperationRoundResult:
    """转向到目标角度，未到位时返回 retry 让节点重入。

    返回 success 仅意味着朝向已就绪，前移、交互等后续动作由调用方自行决定。
    """
    mini_map = operation.ctx.world_patrol_service.cut_mini_map(operation.last_screenshot)
    if not mini_map.play_mask_found:
        return operation.round_retry(status='未识别到小地图', wait=1)

    current_angle = mini_map.view_angle
    if current_angle is None:
        return operation.round_retry(status='识别朝向失败', wait=1)

    angle_diff = cal_utils.angle_delta(current_angle, target_angle)
    if abs(angle_diff) > angle_threshold:
        operation.turn_compensator.turn_from_angle(current_angle, angle_diff)
        return operation.round_retry(status=turn_status, wait=turn_wait)

    return operation.round_success()
