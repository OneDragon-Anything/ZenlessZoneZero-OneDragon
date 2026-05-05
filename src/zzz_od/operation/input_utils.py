import time

from one_dragon.base.controller.pc_controller_base import PcControllerBase
from one_dragon.base.geometry.point import Point


def wake_mouse_at(controller: PcControllerBase, pos: Point, distance: int = 8, interval: float = 0.03) -> None:
    """让游戏先收到鼠标移动，再执行后续点击。"""
    for offset in (Point(-distance, 0), Point(distance, 0), Point(0, 0)):
        controller.mouse_move(pos + offset)
        time.sleep(interval)
