from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from one_dragon.base.geometry.point import Point
from one_dragon.utils import cv2_utils, os_utils

if TYPE_CHECKING:
    from cv2.typing import MatLike

# 武备箱结果两排、安全箱一排格心，来自 2026-09-21 待入箱实拍。
_RESULT_XS: tuple[int, ...] = (1342, 1443, 1543, 1644, 1744)
_SAFE_XS: tuple[int, ...] = (259, 360, 461, 561, 663)
RESULT_SLOT_CENTERS: tuple[Point, ...] = tuple(
    Point(x, y) for y in (330, 431) for x in _RESULT_XS
)
SAFE_SLOT_CENTERS: tuple[Point, ...] = tuple(Point(x, 899) for x in _SAFE_XS)
# 仓库安全箱的位置与局内不同，启动转存、结算及空箱核验共用这一组。
WAREHOUSE_SAFE_CENTERS: tuple[Point, ...] = tuple(Point(x, 897) for x in (267, 371, 475, 579, 683))
_SLOT_HALF: int = 32
# 空格灰度标准差约 4–8；有图标时通常 >40。取中间阈值，避免把轻微噪点当占用。
_OCCUPIED_STD_MIN: float = 20.0
_APPEARANCE_MEAN_DIFF_MIN: float = 12.0
_LOCK_MATCH_MIN: float = 0.9


@dataclass(frozen=True)
class SafeSlotIndices:
    """安全箱按原显示位置编号的占用格、空格和锁定格。"""

    occupied: tuple[int, ...]
    empty: tuple[int, ...]
    locked: tuple[int, ...]


@lru_cache(maxsize=1)
def _safe_lock_template() -> MatLike | None:
    """读取原生截图裁出的锁图标；测试工作目录不含资源时回退到源码仓。"""
    relative = Path('assets/template/bagel/safe_slot_locked/raw.png')
    for root in (Path(os_utils.get_work_dir()), Path(__file__).resolve().parents[4]):
        path = root / relative
        if path.is_file():
            image = cv2_utils.read_image(str(path))
            if image is not None:
                return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    return None


def inspect_safe_slots(
    screen: MatLike, centers: tuple[Point, ...] = SAFE_SLOT_CENTERS,
) -> SafeSlotIndices | None:
    """识别截图控制器已缩放到 1080p 的图像；默认格心仅适用于局内。"""
    template = _safe_lock_template()
    if screen is None or screen.shape != (1080, 1920, 3) or template is None or len(centers) != 5:
        return None
    occupied: list[int] = []
    empty: list[int] = []
    locked: list[int] = []
    for index, center in enumerate(centers):
        search = slot_crop(screen, center, half=48)
        crop = slot_crop(screen, center)
        if search is None or search.shape != (96, 96, 3) or crop is None or crop.shape != (64, 64, 3):
            return None
        gray = cv2.cvtColor(search, cv2.COLOR_RGB2GRAY)
        score = float(cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED).max())
        if score >= _LOCK_MATCH_MIN:
            locked.append(index)
            continue
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        deviation = float(np.std(gray))
        if deviation >= _OCCUPIED_STD_MIN:
            occupied.append(index)
        elif 1 <= deviation <= 9 and 12 <= float(np.mean(gray)) <= 35:
            # 已归档空槽有暗色纹理；锁图标、纯黑遮挡和高亮过渡不能按空槽处理。
            empty.append(index)
        else:
            return None
    capacity = len(occupied) + len(empty)
    if capacity < 2 or locked != list(range(capacity, len(centers))):
        return None
    return SafeSlotIndices(tuple(occupied), tuple(empty), tuple(locked))


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
