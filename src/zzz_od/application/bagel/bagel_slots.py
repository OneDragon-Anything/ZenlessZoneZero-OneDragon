from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np

from one_dragon.base.geometry.point import Point

if TYPE_CHECKING:
    from cv2.typing import MatLike

# 开箱面板卡片实测（1080p 原生截图量得，非估算）：
# 卡片 90x112 一格。结果面板为 5 列 2 排，格心 x 从 1353 起每 100 一列，
# y 为 254 与 380；安全箱为一排 5 格，格心 x 从 259 起每 101 一格，y 883。
# 旧值（结果 y 330/431、安全箱 y 855）是按旧版面板标的，在新面板上会让
# 64x64 采样窗横跨两排卡片，导致空格被判成占用，必须按实测改回。
_RESULT_XS: tuple[int, ...] = (1353, 1453, 1553, 1653, 1753)
_RESULT_YS: tuple[int, ...] = (254, 380)
_SAFE_XS: tuple[int, ...] = (259, 360, 461, 562, 663)
_SAFE_Y: int = 883
RESULT_SLOT_CENTERS: tuple[Point, ...] = tuple(
    Point(x, y) for y in _RESULT_YS for x in _RESULT_XS
)
SAFE_SLOT_CENTERS: tuple[Point, ...] = tuple(Point(x, _SAFE_Y) for x in _SAFE_XS)
# 仓库安全箱的位置与局内不同，启动转存、结算及空箱核验共用这一组。
WAREHOUSE_SAFE_CENTERS: tuple[Point, ...] = tuple(Point(x, 897) for x in (267, 371, 475, 579, 683))
# 卡片 90 宽、列间距 10，采样窗取半边 32（64x64）刚好落在卡片内部。
_SLOT_HALF: int = 32
# 实测：空槽灰度标准差 2.98–3.00，其中带时钟图标的闲置槽也只有 5.54；
# 有图标时 58.37–67.50。阈值取在两者中间，既不会把空槽当占用，
# 也不会漏掉图标面积小的物品。
_OCCUPIED_STD_MIN: float = 20.0
# 空槽还有一层上限，避免把高亮过渡、遮挡或异常画面当成可用的空槽。
_EMPTY_MAX_STD: float = 12.0
_EMPTY_MAX_MEAN: float = 45.0
_APPEARANCE_MEAN_DIFF_MIN: float = 12.0


@dataclass(frozen=True)
class SafeSlotIndices:
    """安全箱按原显示位置编号的占用格与可用空格。

    安全箱五个格子全部可用：格内的时钟图标表示该格闲置，不是锁定，
    因此这里只区分「已占用」和「可以放东西」。
    """

    occupied: tuple[int, ...]
    empty: tuple[int, ...]


def inspect_safe_slots(
    screen: MatLike,
    centers: tuple[Point, ...] = SAFE_SLOT_CENTERS,
) -> SafeSlotIndices | None:
    """识别截图控制器已缩放到 1080p 的图像；默认格心仅适用于局内。

    Args:
        screen: 框架截图，RGB。
        centers: 安全箱格心。
    """
    if screen is None or screen.shape != (1080, 1920, 3) or len(centers) != 5:
        return None
    gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
    occupied: list[int] = []
    empty: list[int] = []
    for index, center in enumerate(centers):
        crop = slot_crop(gray, center)
        if crop is None or crop.shape != (64, 64):
            return None
        deviation = float(np.std(crop))
        if deviation >= _OCCUPIED_STD_MIN:
            occupied.append(index)
        elif deviation <= _EMPTY_MAX_STD and float(np.mean(crop)) <= _EMPTY_MAX_MEAN:
            # 闲置槽里有暗色时钟图标，整体依然很暗、很平，按可用空格处理。
            empty.append(index)
        else:
            return None
    if len(occupied) + len(empty) < 2:
        return None
    return SafeSlotIndices(tuple(occupied), tuple(empty))


def safe_occupied_indices(screen: MatLike) -> tuple[int, ...] | None:
    """仓库安全箱计数共用入口；未知与空箱必须区分。"""
    slots = inspect_safe_slots(screen, WAREHOUSE_SAFE_CENTERS)
    return None if slots is None else slots.occupied


def slot_crop(screen: MatLike, center: Point, half: int = _SLOT_HALF) -> MatLike | None:
    """裁出格子图像；越界时夹到画面内，无效则返回 None。

    Args:
        screen: 框架截图。
        center: 格子中心（1080p 游戏坐标）。
        half: 裁剪半边长。
    """
    x1 = max(0, int(center.x) - half)
    y1 = max(0, int(center.y) - half)
    x2 = min(screen.shape[1], int(center.x) + half)
    y2 = min(screen.shape[0], int(center.y) + half)
    if x2 <= x1 or y2 <= y1:
        return None
    return screen[y1:y2, x1:x2]


def slot_occupied(screen: MatLike, center: Point, half: int = _SLOT_HALF) -> bool:
    """用局部灰度方差判断格子是否有图标；空格接近纯色低方差。

    Args:
        screen: 框架截图，RGB 或 BGR 均可，只取亮度方差。
        center: 格子中心（1080p 游戏坐标）。
        half: 裁剪半边长。
    """
    crop = slot_crop(screen, center, half)
    if crop is None:
        return False
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY) if crop.ndim == 3 else crop
    return float(np.std(gray)) >= _OCCUPIED_STD_MIN


def occupied_indices(screen: MatLike, centers: tuple[Point, ...]) -> list[int]:
    """返回有物品的格子下标，从左到右。"""
    return [index for index, center in enumerate(centers) if slot_occupied(screen, center)]


def empty_indices(screen: MatLike, centers: tuple[Point, ...]) -> list[int]:
    """返回空格子下标，从左到右。"""
    return [index for index, center in enumerate(centers) if not slot_occupied(screen, center)]


def slot_appearance_changed(
    before: MatLike,
    after: MatLike,
    center: Point,
    min_mean_diff: float = _APPEARANCE_MEAN_DIFF_MIN,
) -> bool:
    """格子图像平均绝对差超过阈值则视为外观变了。"""
    first = slot_crop(before, center)
    second = slot_crop(after, center)
    if first is None or second is None or first.shape != second.shape:
        return True
    diff = np.mean(np.abs(first.astype(np.float32) - second.astype(np.float32)))
    return float(diff) >= min_mean_diff


def transfer_visually_ok(
    before: MatLike,
    after: MatLike,
    source: Point,
    destination: Point,
) -> bool:
    """核对一次拖入空格：源格清空且目标格由空变有。不认点击本身。"""
    return (
        slot_occupied(before, source)
        and not slot_occupied(after, source)
        and not slot_occupied(before, destination)
        and slot_occupied(after, destination)
    )


def swap_visually_ok(
    before: MatLike,
    after: MatLike,
    source: Point,
    destination: Point,
) -> bool:
    """核对一次对换：两边拖前拖后都占用，且两边外观都变。"""
    return (
        slot_occupied(before, source)
        and slot_occupied(after, source)
        and slot_occupied(before, destination)
        and slot_occupied(after, destination)
        and slot_appearance_changed(before, after, source)
        and slot_appearance_changed(before, after, destination)
    )