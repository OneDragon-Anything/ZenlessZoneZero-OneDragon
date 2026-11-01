"""拖拽的三段时序，单位为秒。"""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class DragTiming:
    """显式指定拖拽时序；移动时间仍受控制器的最短移动时间限制。

    Attributes:
        press_wait: 按下鼠标后、开始移动前的等待时间。
        move_duration: 鼠标移动时间。
        release_wait: 到达终点后、松开鼠标前的等待时间。
    """

    press_wait: float
    move_duration: float
    release_wait: float

    def __post_init__(self) -> None:
        """在发送输入前拒绝无效时长。"""
        for name in ('press_wait', 'move_duration', 'release_wait'):
            value = getattr(self, name)
            if not isfinite(value) or value < 0:
                raise ValueError(f'{name} 必须是有限的非负数')
