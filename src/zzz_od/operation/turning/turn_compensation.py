from one_dragon.utils import cal_utils
from zzz_od.controller.zzz_pc_controller import ZPcController


class AngleTurnCompensator:
    """运行期角度转向补偿会话，不写回配置。"""

    _ANGLE_EPSILON: float = 1e-6
    _MIN_SCALE: float = 0.5
    _MAX_SCALE: float = 2.0
    _MAX_SCALE_CHANGE: float = 0.1
    _MIN_ANGLE_FOR_REVERSE_UNFOLD: float = 150

    def __init__(self, controller: ZPcController) -> None:
        """创建一份独立的运行期补偿会话。"""
        self.controller: ZPcController = controller
        self.scale: float = 1.0
        # 记录上一轮转向样本，等下一帧拿到新朝向后再学习
        self.last_source_angle: float | None = None
        self.last_effective_angle_diff: float | None = None

    def reset(self) -> None:
        """清空补偿比例和上一轮转向样本。"""
        self.scale = 1.0
        self.clear_pending_sample()

    def clear_pending_sample(self) -> None:
        """清空上一轮尚未学习的转向样本，保留补偿比例。"""
        self.last_source_angle = None
        self.last_effective_angle_diff = None

    def learn(self, source_angle: float, effective_angle_diff: float, current_angle: float) -> None:
        """用转向前后的朝向变化更新运行期补偿比例。"""
        if abs(effective_angle_diff) <= self._ANGLE_EPSILON:
            return

        # 用实际朝向变化反推 scale；转少放大，转多缩小
        observed_angle_change = self._observed_angle_change(
            source_angle,
            effective_angle_diff,
            current_angle,
        )
        if abs(observed_angle_change) <= self._ANGLE_EPSILON or observed_angle_change * effective_angle_diff <= 0:
            return

        scale_change = effective_angle_diff / observed_angle_change - self.scale
        clipped_change = max(-self._MAX_SCALE_CHANGE, min(scale_change, self._MAX_SCALE_CHANGE))
        self.scale = max(self._MIN_SCALE, min(self.scale + clipped_change, self._MAX_SCALE))

    def turn_from_angle(self, source_angle: float, angle_diff: float) -> float:
        """用当前朝向学习上一轮，再下发本轮转向并记录样本。"""
        if self.last_source_angle is not None and self.last_effective_angle_diff is not None:
            self.learn(self.last_source_angle, self.last_effective_angle_diff, source_angle)
        self.last_source_angle = source_angle
        self.last_effective_angle_diff = self.turn(angle_diff)
        return self.last_effective_angle_diff

    def turn(self, angle_diff: float, max_abs_angle_diff: float | None = None) -> float:
        """按当前补偿比例下发转向，返回实际下发角度。"""
        effective_angle_diff = angle_diff * self.scale
        if max_abs_angle_diff is not None:
            effective_angle_diff = max(-max_abs_angle_diff, min(effective_angle_diff, max_abs_angle_diff))
        self.controller.turn_by_angle_diff(effective_angle_diff)
        return effective_angle_diff

    def _observed_angle_change(
        self,
        source_angle: float,
        effective_angle_diff: float,
        current_angle: float,
    ) -> float:
        """计算实际朝向变化，必要时展开跨 180 度的最短角。

        angle_delta 返回 [-180, 180] 的最短角；例如从 0 度转到 185 度会返回 -175。
        只有命令和观测变化都接近 ±180 度时才展开反向观测，小转向反向时保留反号让 learn 跳过。
        """
        observed_angle_change = cal_utils.angle_delta(source_angle, current_angle)
        if observed_angle_change * effective_angle_diff >= 0:
            return observed_angle_change

        if (
            abs(effective_angle_diff) < self._MIN_ANGLE_FOR_REVERSE_UNFOLD
            or abs(observed_angle_change) < self._MIN_ANGLE_FOR_REVERSE_UNFOLD
        ):
            return observed_angle_change
        if effective_angle_diff > 0:
            return observed_angle_change + 360
        return observed_angle_change - 360
