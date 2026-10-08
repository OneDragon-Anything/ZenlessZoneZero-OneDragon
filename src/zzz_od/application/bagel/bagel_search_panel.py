"""确认局内搜查面板的位置与稳定性，不判断物品内容。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from zzz_od.application.bagel.bagel_slots import RESULT_SLOT_CENTERS, SAFE_SLOT_CENTERS

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.geometry.point import Point


def _row_in_position(gray: MatLike, centers: tuple[Point, ...]) -> bool:
    """至少四个完整格框位于预期位置；允许一个格框被鼠标或揭示动画遮住。"""
    left, top = int(centers[0].x) - 70, int(centers[0].y) - 70
    right, bottom = int(centers[-1].x) + 70, int(centers[0].y) + 70
    edges = cv2.Canny(gray[top:bottom, left:right], 40, 100)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    matched: set[int] = set()
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if not (85 <= width <= 105 and 100 <= height <= 120):
            continue
        cx, cy = left + x + width / 2, top + y + height / 2
        for index, center in enumerate(centers):
            if abs(cx - center.x) <= 4 and abs(cy - center.y) <= 4:
                matched.add(index)
    return len(matched) >= 4


def search_panel_pixels(screen: MatLike) -> tuple[MatLike, MatLike] | None:
    """左右格框到位后，提取安全箱标题栏和结果面板侧框，避开物品动画。"""
    if screen is None or screen.shape != (1080, 1920, 3):
        return None
    gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
    if not (_row_in_position(gray, SAFE_SLOT_CENTERS)
            and _row_in_position(gray, RESULT_SLOT_CENTERS[:5])):
        return None
    return gray[800:837, 210:715].copy(), gray[195:520, 1250:1275].copy()


class SearchPanelGuard:
    """只有连续两张新截图均到位且静态区域变化很小，才允许处理物品。"""

    def __init__(self) -> None:
        """首次观察必须等待下一张截图。"""
        self._pixels: tuple[MatLike, MatLike] | None = None
        self._screenshot_time: float | None = None

    def reset(self) -> None:
        """画面不明或已经发送拖拽后，重新建立连续截图基线。"""
        self._pixels = None
        self._screenshot_time = None

    def observe(self, screen: MatLike, screenshot_time: float) -> bool:
        """重复截图不算稳定证据；位置不符时立即丢弃旧基线。"""
        if self._screenshot_time is not None and screenshot_time <= self._screenshot_time:
            return False
        pixels = search_panel_pixels(screen)
        if pixels is None:
            self.reset()
            return False
        previous = self._pixels
        self._pixels = pixels
        self._screenshot_time = screenshot_time
        return previous is not None and all(
            float(np.abs(before.astype(np.float32) - after.astype(np.float32)).mean()) < 4
            for before, after in zip(previous, pixels, strict=True)
        )
