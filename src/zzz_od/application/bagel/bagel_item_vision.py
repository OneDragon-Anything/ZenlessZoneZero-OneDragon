from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from one_dragon.base.geometry.point import Point
from one_dragon.utils import cv2_utils, os_utils
from zzz_od.application.bagel.bagel_slots import slot_crop, slot_occupied

if TYPE_CHECKING:
    from cv2.typing import MatLike

# 品质从高到低；未对上的底色为未知，最低，有空格时仍可装入。
QUALITY_RANK: dict[str, int] = {'Z': 5, 'S': 4, 'A': 3, 'B': 2, 'C': 1, '?': 0}
ITEM_TYPE_OTHER: str = '其他'
ITEM_TYPE_CURRENCY: str = '金币'
QUALITY_UNKNOWN: str = '?'

# 同品质时的类型顺序，来自仓库「快速选择」名称。
TYPE_RANK: dict[str, int] = {
    '贵重物品': 5,
    '战术棱镜': 4,
    '装备': 3,
    '门禁卡': 2,
    '战术道具': 1,
    ITEM_TYPE_OTHER: 0,
    '材料': -1,
    ITEM_TYPE_CURRENCY: -2,
}

ACTION_FILL: str = 'fill'
ACTION_SWAP: str = 'swap'

# 角标在格心左上；占用裁剪（半边 32）往往切不到角标，单独开搜索窗。
_BADGE_OFFSET: int = 60
_BADGE_SEARCH: int = 48
_BADGE_MATCH_MIN: float = 0.75
# OpenCV HSV：H 0–180。红=Z、金=S、紫=A、蓝=B、绿=C。
_QUALITY_S_MIN: float = 40.0
_QUALITY_V_MIN: float = 40.0

_BADGE_FILES: tuple[tuple[str, str], ...] = (
    (ITEM_TYPE_CURRENCY, 'currency'),
    ('战术道具', 'tactic'),
    ('战术棱镜', 'prism_bell'),
    ('战术棱镜', 'prism_char'),
    ('装备', 'equip'),
    ('贵重物品', 'valuable'),
    ('门禁卡', 'keycard'),
    # 历史文件 other 也是白色箱子材料角标，不能因匹配到不同实拍而改变优先级。
    ('材料', 'other'),
    ('材料', 'material'),
)


@dataclass(frozen=True)
class BagelSlotMark:
    """已占用格子上读到的品质与类型。"""

    index: int
    center: Point
    quality: str
    item_type: str

    @property
    def quality_rank(self) -> int:
        """品质排序值，未知为 0。"""
        return QUALITY_RANK.get(self.quality, 0)

    @property
    def type_rank(self) -> int:
        """类型排序值；未识别按其他。"""
        return TYPE_RANK.get(self.item_type, 0)

    @property
    def priority(self) -> tuple[bool, int, int]:
        """金币最低；材料低于所有其他物品，非材料先比品质再比类型。"""
        if self.item_type == ITEM_TYPE_CURRENCY:
            return False, -1, self.type_rank
        return (self.item_type != '材料', self.quality_rank, self.type_rank)


@dataclass(frozen=True)
class StoreChoice:
    """下一件拖拽：填入空安全箱，或与箱内更差的一格对换。"""

    kind: str
    source_index: int
    dest_index: int
    mark: BagelSlotMark


def is_strictly_better(left: BagelSlotMark, right: BagelSlotMark) -> bool:
    """先区分材料，再比品质和类型，相等则不替换。"""
    return left.priority > right.priority


def identify_quality(crop: MatLike) -> str:
    """用格子底色的 HSV 中位数判断 Z/S/A/B/C；对不上则为未知。

    Args:
        crop: 格子占用裁剪，RGB。
    """
    if crop.ndim != 3 or crop.size == 0:
        return QUALITY_UNKNOWN
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    hue, saturation, value = np.median(hsv.reshape(-1, 3), axis=0)
    if saturation < _QUALITY_S_MIN or value < _QUALITY_V_MIN:
        return QUALITY_UNKNOWN
    if hue <= 12 or hue >= 165:
        return 'Z'
    if 16 <= hue <= 42:
        return 'S'
    if 120 <= hue <= 160:
        return 'A'
    if 90 <= hue <= 119:
        return 'B'
    if 50 <= hue <= 85:
        return 'C'
    return QUALITY_UNKNOWN


def identify_type(screen: MatLike, center: Point) -> str:
    """在格心左上搜索角标模板；低于阈值视为其他。

    Args:
        screen: 整屏 RGB。
        center: 格子中心。
    """
    crop = _badge_search_crop(screen, center)
    if crop is None:
        return ITEM_TYPE_OTHER
    best_type = ITEM_TYPE_OTHER
    best_score = -1.0
    for item_type, template in _badge_templates():
        if crop.shape[0] < template.shape[0] or crop.shape[1] < template.shape[1]:
            continue
        score = float(cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED).max())
        if score > best_score:
            best_score = score
            best_type = item_type
    if best_score < _BADGE_MATCH_MIN:
        return ITEM_TYPE_OTHER
    return best_type


def inspect_occupied(screen: MatLike, centers: tuple[Point, ...]) -> list[BagelSlotMark]:
    """只识别已占用格子的品质和类型。

    Args:
        screen: 整屏 RGB。
        centers: 结果格、安全箱或背包格心。
    """
    marks: list[BagelSlotMark] = []
    for index, center in enumerate(centers):
        if not slot_occupied(screen, center):
            continue
        crop = slot_crop(screen, center, half=40)
        if crop is None or crop.shape[:2] != (80, 80):
            continue
        # 格心图案会遮住底色；只取左右色带，避开左上角标和底部数量。
        background = np.concatenate((crop[6:55, 2:7], crop[6:55, 73:78]), axis=1)
        marks.append(
            BagelSlotMark(
                index=index,
                center=center,
                quality=identify_quality(background),
                item_type=identify_type(screen, center),
            ),
        )
    return marks


def choose_store_action(
    results: Sequence[BagelSlotMark],
    safes: Sequence[BagelSlotMark],
    safe_empty: Sequence[int],
) -> StoreChoice | None:
    """挑选一件非金币结果；安全箱满时仅严格更优的物品可以对换。"""
    candidates = [mark for mark in results if mark.item_type != ITEM_TYPE_CURRENCY]
    if not candidates:
        return None
    candidate = max(
        candidates,
        key=lambda mark: (*mark.priority, -mark.index),
    )
    if safe_empty:
        return StoreChoice(ACTION_FILL, candidate.index, safe_empty[0], candidate)
    if safes:
        worst = min(
            safes,
            key=lambda mark: (*mark.priority, mark.index),
        )
        if is_strictly_better(candidate, worst):
            return StoreChoice(ACTION_SWAP, candidate.index, worst.index, candidate)
    return None


def _badge_search_crop(screen: MatLike, center: Point) -> MatLike | None:
    """裁出格心左上的角标搜索窗。"""
    x1 = int(center.x) - _BADGE_OFFSET
    y1 = int(center.y) - _BADGE_OFFSET
    x2 = x1 + _BADGE_SEARCH
    y2 = y1 + _BADGE_SEARCH
    if x1 < 0 or y1 < 0 or x2 > screen.shape[1] or y2 > screen.shape[0]:
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(screen.shape[1], x2)
        y2 = min(screen.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return screen[y1:y2, x1:x2]


@lru_cache(maxsize=1)
def _badge_templates() -> tuple[tuple[str, MatLike], ...]:
    """从资源目录加载角标模板；缺文件的类型跳过。"""
    loaded: list[tuple[str, MatLike]] = []
    directory = _badge_dir()
    for item_type, stem in _BADGE_FILES:
        image = cv2_utils.read_image(str(directory / f'{stem}.png'))
        if image is None:
            continue
        loaded.append((item_type, image))
    return tuple(loaded)


def _badge_dir() -> Path:
    """工作目录有模板则用；测试临时目录没有时回退到仓库 assets。"""
    relative = Path('assets') / 'game_data' / 'bagel' / 'item_badges'
    candidates = (
        Path(os_utils.get_work_dir()) / relative,
        Path(__file__).resolve().parents[4] / relative,
    )
    for directory in candidates:
        if directory.is_dir() and any(directory.glob('*.png')):
            return directory
    return candidates[0]
