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
from zzz_od.application.bagel.bagel_slots import slot_occupied

if TYPE_CHECKING:
    from cv2.typing import MatLike

# 品质从高到低；未对上的底色为未知，最低，有空格时仍可装入。
QUALITY_RANK: dict[str, int] = {'Z': 5, 'S': 4, 'A': 3, 'B': 2, 'C': 1, '?': 0}
ITEM_TYPE_OTHER: str = '其他'
ITEM_TYPE_CURRENCY: str = '金币'
ITEM_TYPE_BLUEPRINT: str = '蓝图'
# 特殊奖励专指使用切面钻石角标的菲林、零号业绩，不代表全部撤离奖励。
ITEM_TYPE_SPECIAL_REWARD: str = '特殊奖励'
QUALITY_UNKNOWN: str = '?'

# 同组、同品质时的类型顺序；两种蓝图开关状态共用。
TYPE_RANK: dict[str, int] = {
    ITEM_TYPE_SPECIAL_REWARD: 7,
    '贵重物品': 6,
    ITEM_TYPE_BLUEPRINT: 5,
    '门禁卡': 4,
    '战术棱镜': 3,
    '装备': 2,
    '战术道具': 1,
    ITEM_TYPE_OTHER: 0,
    '材料': -1,
    ITEM_TYPE_CURRENCY: -2,
}

ACTION_FILL: str = 'fill'
ACTION_SWAP: str = 'swap'

# 相对已校准格心，36x36 搜索窗完整覆盖 24x24 / 24x26 模板并保留边缘余量。
_BADGE_LEFT: int = 56
_BADGE_TOP: int = 64
_BADGE_SEARCH: int = 36
_BADGE_MATCH_MIN: float = 0.75
# OpenCV HSV：H 0–180。红=Z、金=S、紫=A、蓝=B、绿=C。
_QUALITY_S_MIN: float = 40.0
_QUALITY_V_MIN: float = 40.0
# 品质只读左右底色，避开中央图案、左上角标和下方数量/等级文字。
# 每条 6x48；外侧内缩两像素，减少格心误差导致取到黑边的机会。
_QUALITY_REGIONS: tuple[tuple[int, int, int, int], ...] = (
    (-36, -28, -30, 20),
    (30, -28, 36, 20),
)

_BADGE_FILES: tuple[tuple[str, str], ...] = (
    (ITEM_TYPE_BLUEPRINT, 'blueprint'),
    (ITEM_TYPE_CURRENCY, 'currency'),
    ('战术道具', 'tactic'),
    ('战术棱镜', 'prism_bell'),
    ('战术棱镜', 'prism_char'),
    ('装备', 'equip'),
    ('装备', 'backpack'),
    ('贵重物品', 'valuable'),
    (ITEM_TYPE_SPECIAL_REWARD, 'valuable_reward'),
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

    def priority(self, blueprint_priority: bool = True) -> tuple[int, int, int]:
        """先分组，再比品质和类型；开启时蓝图独立分组且只比品质。"""
        if self.item_type == ITEM_TYPE_CURRENCY:
            return -1, -1, self.type_rank
        if blueprint_priority and self.item_type == ITEM_TYPE_BLUEPRINT:
            return 2, self.quality_rank, 0
        if self.item_type == '材料':
            return 0, self.quality_rank, self.type_rank
        return 1, self.quality_rank, self.type_rank


@dataclass(frozen=True)
class StoreChoice:
    """下一件拖拽：填入空安全箱，或与箱内更差的一格对换。"""

    kind: str
    source_index: int
    dest_index: int
    mark: BagelSlotMark


def is_strictly_better(
    left: BagelSlotMark,
    right: BagelSlotMark,
    blueprint_priority: bool = True,
) -> bool:
    """按同一开关比较两件物品，优先级相等则不替换。"""
    return left.priority(blueprint_priority) > right.priority(blueprint_priority)


def identify_quality(screen: MatLike, center: Point) -> str:
    """用左右底色色带的 HSV 中位数判断 Z/S/A/B/C；对不上则为未知。

    Args:
        screen: 整屏 RGB。
        center: 格子中心。
    """
    regions: list[MatLike] = []
    for left, top, right, bottom in _QUALITY_REGIONS:
        x1, y1 = int(center.x) + left, int(center.y) + top
        x2, y2 = int(center.x) + right, int(center.y) + bottom
        if x1 < 0 or y1 < 0 or x2 > screen.shape[1] or y2 > screen.shape[0]:
            return QUALITY_UNKNOWN
        regions.append(screen[y1:y2, x1:x2])
    hsv = cv2.cvtColor(np.concatenate(regions, axis=1), cv2.COLOR_RGB2HSV)
    hue, sat, value = (float(value) for value in np.median(hsv.reshape(-1, 3), axis=0))
    if sat < _QUALITY_S_MIN or value < _QUALITY_V_MIN:
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


def inspect_occupied(
    screen: MatLike,
    centers: tuple[Point, ...],
    indices: Sequence[int] | None = None,
) -> list[BagelSlotMark]:
    """只识别已占用格子的品质和类型。

    Args:
        screen: 整屏 RGB。
        centers: 结果格、安全箱或背包格心。
        indices: 只识别这些下标；None 表示按灰度方差自行判断哪些格子有物品。
    """
    marks: list[BagelSlotMark] = []
    for index, center in enumerate(centers):
        if indices is not None:
            if index not in indices:
                continue
        elif not slot_occupied(screen, center):
            continue
        marks.append(
            BagelSlotMark(
                index=index,
                center=center,
                quality=identify_quality(screen, center),
                item_type=identify_type(screen, center),
            ),
        )
    return marks


def choose_store_action(
    results: Sequence[BagelSlotMark],
    safes: Sequence[BagelSlotMark],
    safe_empty: Sequence[int],
    blueprint_priority: bool = True,
) -> StoreChoice | None:
    """用同一优先级选择非金币候选和箱内目标；满箱时仅严格更优才对换。"""
    candidates = [mark for mark in results if mark.item_type != ITEM_TYPE_CURRENCY]
    if not candidates:
        return None
    candidate = max(
        candidates,
        key=lambda mark: (*mark.priority(blueprint_priority), -mark.index),
    )
    if safe_empty:
        return StoreChoice(ACTION_FILL, candidate.index, safe_empty[0], candidate)
    if safes:
        worst = min(
            safes,
            key=lambda mark: (*mark.priority(blueprint_priority), mark.index),
        )
        if is_strictly_better(candidate, worst, blueprint_priority):
            return StoreChoice(ACTION_SWAP, candidate.index, worst.index, candidate)
    return None


def _badge_search_crop(screen: MatLike, center: Point) -> MatLike | None:
    """裁出格心左上的角标搜索窗。"""
    x1 = int(center.x) - _BADGE_LEFT
    y1 = int(center.y) - _BADGE_TOP
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
