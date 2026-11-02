from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

import cv2
import numpy as np

if TYPE_CHECKING:
    from cv2.typing import MatLike


@dataclass
class LostVoidStuckState:
    """同一楼层共享的连续受阻次数和相对镜头方向记忆。"""

    DIRECTIONS: ClassVar[tuple[str, ...]] = (
        'a', 'd', 'sa', 'sd', 's', 'wa', 'wd', 'w',
    )

    stuck_times: int = 0
    prefer_left_escape: bool = True
    direction_penalties: dict[str, int] = field(default_factory=dict)
    last_direction: str = 'w'
    attack_attempted: bool = False
    recovery_active: bool = False

    def record_stuck(self) -> None:
        """增加连续受阻次数，并惩罚上次没有带来进展的方向。"""
        self.stuck_times += 1
        self.recovery_active = True
        self.penalize_direction(self.last_direction)

    def penalize_direction(self, direction: str) -> None:
        """记录一次方向试走失败。"""
        self.direction_penalties[direction] = (
            self.direction_penalties.get(direction, 0) + 1
        )

    def choose_direction(self) -> str:
        """优先尝试失败次数最少的方向，同分时交替偏向左右。"""
        directions = self.DIRECTIONS
        if not self.prefer_left_escape:
            directions = tuple(
                direction.translate(str.maketrans('ad', 'da'))
                for direction in directions
            )
        direction = min(
            directions, key=lambda value: self.direction_penalties.get(value, 0),
        )
        self.last_direction = direction
        self.prefer_left_escape = not self.prefer_left_escape
        return direction

    def record_progress(self) -> None:
        """脱困前允许场景移动清理计数，脱困中需等实际到达再清理。"""
        if self.recovery_active:
            return
        self.stuck_times = 0
        self.attack_attempted = False
        self.last_direction = 'w'

    def record_arrival(self) -> None:
        """实际到达或进入交互、战斗后结束脱困，保留本层方向记忆。"""
        self.recovery_active = False
        self.record_progress()


class LostVoidMotionDetector:
    """用固定镜头下的中心场景帧差判断前进是否有效。"""

    # 下方中央留给宽翼、武器和跑步动画，分区只观察周围场景。
    SCENE_REGIONS: ClassVar[tuple[tuple[int, int, int, int], ...]] = (
        (0, 0, 40, 30), (40, 0, 80, 30),
        (80, 0, 120, 30), (120, 0, 160, 30),
        (0, 30, 40, 60), (120, 30, 160, 60),
        (0, 60, 40, 90), (120, 60, 160, 90),
    )

    def __init__(
        self,
        sample_interval: float,
        static_seconds: float,
        motion_threshold: float,
    ) -> None:
        """初始化采样间隔、受阻持续时间与变化像素占比阈值。"""
        self.sample_interval: float = max(0.1, sample_interval)
        self.static_threshold: float = max(self.sample_interval, static_seconds)
        self.motion_threshold: float = min(1.0, max(0.001, motion_threshold))
        self.last_frame: MatLike | None = None
        self.last_sample_time: float = 0
        self.static_seconds: float = 0
        self.settle_until: float = 0
        self.sampled: bool = False
        self.last_motion_ratio: float = 0
        self.last_region_ratios: tuple[float, ...] = ()
        self.last_sample_state: str = '尚未采样'

    def reset(self, settle_until: float = 0, preserve_static: bool = False) -> None:
        """丢弃旧帧；转镜头时可以保留此前有效采样累积的受阻时间。"""
        self.last_frame = None
        self.last_sample_time = 0
        self.settle_until = settle_until
        self.sampled = False
        self.last_sample_state = '重新采样'
        if not preserve_static:
            self.static_seconds = 0

    @staticmethod
    def prepare_frame(image: MatLike) -> MatLike:
        """缩小、灰度化并模糊中心区域，减少渲染噪声。"""
        small = cv2.resize(image, (160, 90), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
        return cv2.GaussianBlur(gray, (5, 5), 0)

    @staticmethod
    def region_motion_ratios(previous: MatLike, current: MatLike) -> tuple[float, ...]:
        """分别计算八个场景分区的变化比例，排除中央的大型角色动画。"""
        changed = cv2.absdiff(previous, current) > 12
        return tuple(
            float(np.count_nonzero(changed[y1:y2, x1:x2]) / ((x2 - x1) * (y2 - y1)))
            for x1, y1, x2, y2 in LostVoidMotionDetector.SCENE_REGIONS
        )

    @staticmethod
    def motion_ratio(previous: MatLike, current: MatLike) -> float:
        """取第三大的分区变化比例，要求变化同时出现在至少三个区域。"""
        ratios = LostVoidMotionDetector.region_motion_ratios(previous, current)
        return sorted(ratios, reverse=True)[2]

    def update(self, image: MatLike, screenshot_time: float) -> bool | None:
        """返回是否有场景移动；尚未到采样时间时返回空值。"""
        self.sampled = False
        if screenshot_time < self.settle_until:
            self.last_sample_state = '等待镜头稳定'
            return None
        elapsed = screenshot_time - self.last_sample_time
        if self.last_frame is not None and elapsed < self.sample_interval:
            self.last_sample_state = '等待采样间隔'
            return None
        frame = self.prepare_frame(image)
        if self.last_frame is None or elapsed > max(2.0, self.sample_interval * 3):
            if self.last_frame is not None:
                self.static_seconds = 0
                self.last_sample_state = '采样中断，重取基准'
            else:
                self.last_sample_state = '建立基准帧'
            self.last_frame = frame
            self.last_sample_time = screenshot_time
            return None
        self.last_region_ratios = self.region_motion_ratios(self.last_frame, frame)
        self.last_motion_ratio = sorted(self.last_region_ratios, reverse=True)[2]
        self.last_frame = frame
        self.last_sample_time = screenshot_time
        self.sampled = True
        moved = self.last_motion_ratio >= self.motion_threshold
        self.last_sample_state = '场景移动' if moved else '场景静止'
        self.static_seconds = 0 if moved else self.static_seconds + elapsed
        return moved

    @property
    def is_stuck(self) -> bool:
        """判断累计的有效静止时间是否达到阈值。"""
        return self.static_seconds >= self.static_threshold
