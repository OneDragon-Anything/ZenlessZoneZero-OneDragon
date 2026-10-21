"""确认开箱面板是否已经铺开并静下来，不判断物品内容。

旧实现用 Canny 轮廓按 85–105 x 100–120 的框去「找卡片」来确认栅格到位，
那一组尺寸与排距都是针对旧版面板卡的。新版卡片为 90x112、排距也变了，
轮廓再也命不中，于是整个面板永远被判定为「不到位」，`装入安全箱` 会一直
空转到 `DRAG_REPEAT_LIMIT` 之外的那次超时（日志表现为连续打印
「等待搜查面板到位并稳定」然后报「搜查面板状态持续不明」）。

这里改为直接比对画面区域：面板是否打开由 OCR 判据（容器标题、安全箱标题、
全部拾取）确认，本模块只负责确认面板已经铺开并且静下来可以安全拖拽。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from cv2.typing import MatLike

# 取样带（1080p 实测）：
#   结果区——边界正好是结果格栅格的外沿（x 1306–1801、y 205–430），
#           物品进出结果格、翻页都会让它变化；两局内容不同时差异 28.07。
#   面板标题栏——标题文字下方的纯色空白，两局之间差异 0.00，完全静止。
# 前者负责「画面变了就得重新等」，后者负责「这是个已经在位的稳定面板」。
_RESULT_REGION: tuple[slice, slice] = (slice(205, 430), slice(1306, 1801))
_TITLE_REGION: tuple[slice, slice] = (slice(156, 178), slice(1520, 1740))
# 两帧之间区域平均绝对差的下限。静置的同一画面为 0；换一局内容不同的
# 画面为 28.07；拖拽过程中物品移动、格位高亮都会远超这个值。
_STABLE_MAX_DIFF: float = 6.0


def _region(gray: MatLike, region: tuple[slice, slice]) -> MatLike:
    """按预设区域裁出灰度取样带。"""
    rows, cols = region
    return gray[rows, cols].copy()


def search_panel_pixels(screen: MatLike) -> tuple[MatLike, MatLike] | None:
    """提取结果区与面板标题栏两块取样带，供稳定性比对。"""
    if screen is None or screen.shape != (1080, 1920, 3):
        return None
    gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
    return _region(gray, _RESULT_REGION), _region(gray, _TITLE_REGION)


def _regions_stable(
    previous: tuple[MatLike, MatLike],
    current: tuple[MatLike, MatLike],
) -> bool:
    """两块取样带的平均绝对差都必须足够小。"""
    return all(
        float(np.abs(before.astype(np.float32) - after.astype(np.float32)).mean())
        < _STABLE_MAX_DIFF
        for before, after in zip(previous, current, strict=True)
    )


class SearchPanelGuard:
    """只有连续两张新截图的内容都基本一致，才允许处理物品。"""

    def __init__(self) -> None:
        """首次观察必须等待下一张截图。"""
        self._pixels: tuple[MatLike, MatLike] | None = None
        self._screenshot_time: float | None = None

    def reset(self) -> None:
        """画面不明或已经发送拖拽后，重新建立连续截图基线。"""
        self._pixels = None
        self._screenshot_time = None

    def observe(self, screen: MatLike, screenshot_time: float) -> bool:
        """重复截图不算稳定证据；取不到取样带时立即丢弃旧基线。"""
        if self._screenshot_time is not None and screenshot_time <= self._screenshot_time:
            return False
        pixels = search_panel_pixels(screen)
        if pixels is None:
            self.reset()
            return False
        previous = self._pixels
        self._pixels = pixels
        self._screenshot_time = screenshot_time
        return previous is not None and _regions_stable(previous, pixels)