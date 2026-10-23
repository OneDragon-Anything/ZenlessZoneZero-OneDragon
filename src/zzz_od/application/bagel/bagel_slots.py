from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np

from one_dragon.base.geometry.point import Point

if TYPE_CHECKING:
    from cv2.typing import MatLike

# 古怪试炼的 1080p 标准图：结果卡片外框约 92x109，列距约 101、行距 121。
# 两组已知结果格中心 y 为 245/366 与 256/377；基准坐标须经边框定位后使用。
# 局内安全箱外框约 94x111，格心 y=898；仓库继续使用独立坐标。
_RESULT_XS: tuple[int, ...] = (1353, 1453, 1554, 1655, 1756)
_RESULT_YS: tuple[int, ...] = (256, 377)
_SAFE_XS: tuple[int, ...] = (259, 360, 461, 562, 663)
_SAFE_Y: int = 898
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

# 结果格的三种状态。
SLOT_ITEM: str = '有物品'
SLOT_EMPTY: str = '空'
SLOT_LOADING: str = '加载中'

# 结果格判据：只看卡片底部那一小条方框内三通道的最大值。
# 实测四帧：空格与未揭示的格子最大 27–60（底色和底部短横线都不过百），
# 有物品的格子 255（物品高光与堆叠数字），两者之间空档很大。
# 方框放在卡片下沿内侧，横向居中；结果格被选中时的光标亮条在卡片左边缘，
# 落不进这个方框，不会把空格读成有物品。
_ITEM_BOX_HALF_W: int = 16
_ITEM_BOX_TOP: int = 31
_ITEM_BOX_BOTTOM: int = 47
_ITEM_MAX_CHANNEL: int = 240
# 低于这个值算「加载中」：格子还没画出东西，整条方框接近纯黑。
_LOADING_MAX_CHANNEL: int = 40


def locate_result_centers(screen: MatLike) -> tuple[Point, ...] | None:
    """在新赛季面板的有限范围内按两排外框确认格心。

    每排至少三个不同列的完整外框须支持同一纵向偏移。只校正已知面板的
    小幅上下位移，不搜索任意位置；旧赛季面板、遮挡或过渡不能回退到固定格心。
    """
    if screen is None or screen.shape != (1080, 1920, 3):
        return None
    gray = cv2.cvtColor(screen[170:445, 1290:1820], cv2.COLOR_RGB2GRAY)
    contours, _ = cv2.findContours(cv2.Canny(gray, 40, 100), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[int, int, float, int]] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if not (88 <= width <= 98 and 105 <= height <= 115):
            continue
        cx = 1290 + x + (width - 1) / 2
        cy = 170 + y + (height - 1) / 2
        column = min(range(5), key=lambda index: abs(cx - _RESULT_XS[index]))
        row = min(range(2), key=lambda index: abs(cy - _RESULT_YS[index]))
        offset = cy - _RESULT_YS[row]
        if abs(cx - _RESULT_XS[column]) <= 4 and -16 <= offset <= 4:
            candidates.append((row, column, offset, abs(width - 92) + abs(height - 109)))
    best: dict[tuple[int, int], tuple[float, int]] = {}
    best_rank: tuple[int, int] = (0, 0)
    for offset in range(-16, 5):
        group: dict[tuple[int, int], tuple[float, int]] = {}
        for row, column, observed, error in candidates:
            if abs(observed - offset) > 1.5:
                continue
            key = (row, column)
            if key not in group or error < group[key][1]:
                group[key] = (observed, error)
        if any(sum(key[0] == row for key in group) < 3 for row in range(2)):
            continue
        rank = (len(group), -sum(value[1] for value in group.values()))
        if rank > best_rank:
            best, best_rank = group, rank
    if not best:
        return None
    observed = float(np.median([value[0] for value in best.values()]))
    # 压缩、抗锯齿或高亮会使轮廓跳动一像素；只接受已量测的两种排布。
    shift = min((-11, 0), key=lambda value: abs(value - observed))
    if abs(shift - observed) > 2:
        return None
    return tuple(Point(x, y + shift) for y in _RESULT_YS for x in _RESULT_XS)


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


def slot_max_channel(screen: MatLike, center: Point) -> int | None:
    """卡片底部方框内三通道的最大值；越界返回 None。

    方框只取卡片下沿内侧一条，横向以格心居中。结果格被选中时的光标亮条
    压在卡片左边缘，落不进这个方框，不会把空格读成有物品。

    Args:
        screen: 框架截图，RGB。
        center: 格心（1080p 游戏坐标）。
    """
    x1 = int(center.x) - _ITEM_BOX_HALF_W
    x2 = int(center.x) + _ITEM_BOX_HALF_W
    y1 = int(center.y) + _ITEM_BOX_TOP
    y2 = int(center.y) + _ITEM_BOX_BOTTOM
    if x1 < 0 or y1 < 0 or x2 > screen.shape[1] or y2 > screen.shape[0]:
        return None
    return int(screen[y1:y2, x1:x2].max())


def slot_state(screen: MatLike, center: Point) -> str | None:
    """按底部方框最大值分三档；越界返回 None。

    Args:
        screen: 框架截图，RGB。
        center: 格心（1080p 游戏坐标）。
    """
    value = slot_max_channel(screen, center)
    if value is None:
        return None
    if value >= _ITEM_MAX_CHANNEL:
        return SLOT_ITEM
    if value < _LOADING_MAX_CHANNEL:
        return SLOT_LOADING
    return SLOT_EMPTY


def slot_states(screen: MatLike, centers: tuple[Point, ...]) -> list[str | None]:
    """按三态识别一排格子，判不出的格子为 None。

    Args:
        screen: 框架截图，RGB。
        centers: 格心（1080p 游戏坐标）。
    """
    return [slot_state(screen, center) for center in centers]


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
