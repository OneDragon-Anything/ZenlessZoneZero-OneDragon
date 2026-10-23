"""确认新赛季结果面板的位置与稳定性，不代替单格亮度和角标判断。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from zzz_od.application.bagel.bagel_slots import locate_result_centers

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.geometry.point import Point

# 覆盖结果格 y=245/366 与 256/377 两种高度，标题区域避开容器名称。
_RESULT_REGION: tuple[slice, slice] = (slice(188, 433), slice(1306, 1803))
_TITLE_REGION: tuple[slice, slice] = (slice(156, 168), slice(1520, 1740))
_STABLE_MAX_DIFF: float = 6.0


def _region(gray: MatLike, region: tuple[slice, slice]) -> MatLike:
    """按预设区域裁出灰度取样带。"""
    rows, cols = region
    return gray[rows, cols].copy()


def search_panel_pixels(screen: MatLike) -> tuple[MatLike, MatLike] | None:
    """提取结果区与标题空白带，供连续截图比对。"""
    if screen is None or screen.shape != (1080, 1920, 3):
        return None
    gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
    return _region(gray, _RESULT_REGION), _region(gray, _TITLE_REGION)


def _regions_stable(
    previous: tuple[MatLike, MatLike],
    current: tuple[MatLike, MatLike],
) -> bool:
    """分别比较两块取样带，防止多数不变像素掩盖整块区域变化。"""
    return all(
        float(np.abs(before.astype(np.float32) - after.astype(np.float32)).mean())
        < _STABLE_MAX_DIFF
        for before, after in zip(previous, current, strict=True)
    )


class SearchPanelGuard:
    """两张新截图的格心一致且区域变化足够小，才允许处理物品。"""

    def __init__(self) -> None:
        """首次观察必须等待下一张截图。"""
        self._pixels: tuple[MatLike, MatLike] | None = None
        self._screenshot_time: float | None = None
        self.result_centers: tuple[Point, ...] | None = None

    def reset(self) -> None:
        """画面不明或发出拖拽后，重新建立格心和连续截图基线。"""
        self._pixels = None
        self._screenshot_time = None
        self.result_centers = None

    def observe(self, screen: MatLike, screenshot_time: float) -> bool:
        """不接受重复截图、未定位的外框或两帧间仍在移动的格子。"""
        if self._screenshot_time is not None and screenshot_time <= self._screenshot_time:
            return False
        centers = locate_result_centers(screen)
        pixels = search_panel_pixels(screen)
        if centers is None or pixels is None:
            self.reset()
            return False
        previous, previous_centers = self._pixels, self.result_centers
        self._pixels = pixels
        self.result_centers = centers
        self._screenshot_time = screenshot_time
        if previous is None or previous_centers is None:
            return False
        if tuple(point.tuple() for point in previous_centers) != tuple(point.tuple() for point in centers):
            return False
        return _regions_stable(previous, pixels)
