"""小地图镜头朝向识别。

流程：
1. 先 H 滤黄、再 S 滑窗求镜头朝向：圆心用几何中心 (100, 100)，
   即角色位置，不再检测菱形；H 14~34 先拦掉
   白天蓝底，门内每圈 360 点取 S 剖面，117 度宽的楔子滑一圈，
   楔内 S 和最大的位置即朝向。先取 23、28 两圈，
   差 3 度内直接平均收；否则按甜点区顺序加圈，出现 3 圈互差 4 度内即平均收。
   黄底上门约等于直通，退化成纯 S；白天门把蓝底拦掉才不偏。

角度约定：正右为 0，逆时针增加，取值 0~360。

本模块是插件 plugins/map_overlay 朝向算法的独立移植，两边不共享代码。
"""

from __future__ import annotations

import math

import cv2
import numpy as np
from cv2.typing import MatLike

SECTOR_CENTER_OFFSET: tuple[float, float] = (0.0, 0.0)
"""镜头圆心相对几何中心的偏移。201 图几何中心 (100, 100)，直接使用。"""

SECTOR_WEDGE_WIDTH: float = 117.0
"""滑窗楔宽。5 张样本张角 115~119，均值 117；扇形角宽固定，只转中线。"""

SECTOR_STEP_DEGREE: float = 1.0
"""滑窗采样步长。2 度版有张贴线到 2.8 度，1 度压到 1.3，耗时一样。"""

SECTOR_RING_ORDER: list[int] = [23, 28, 24, 30, 22, 26, 25, 27, 29, 31, 32, 33]
"""渐进取圈顺序。22~33 是甜点区（单圈最大 3.3 度内）；34 及外圈崩到 30 度以上，
21 内圈散，不进。先取前两圈，不稳再往后加。"""

SECTOR_YELLOW_H_MIN: float = 14.0
"""黄门下限。扇形 24，黄底 21~23 也在门内（门在黄底上约等于直通）；
白天蓝底 100 直接拦掉。"""

SECTOR_YELLOW_H_MAX: float = 34.0
"""黄门上限。同上。"""

SECTOR_TWO_DIFF: float = 3.0
"""两圈稳定线：差它以内直接平均收。人工误差红线 3 度。"""

SECTOR_GROUP_DEGREE: float = 4.0
"""稳定组半径：3 圈互差它以内即收敛取平均。"""


def _angle_delta(first: float, second: float) -> float:
    """两角度的有符号差，收到 (-180, 180]。"""
    return (first - second + 180.0) % 360.0 - 180.0


def _circular_mean(angles: list[float]) -> float:
    """方向矢量平均，避免 0/360 接缝被拉偏。"""
    sum_x = float(sum(math.cos(math.radians(a)) for a in angles))
    sum_y = float(sum(math.sin(math.radians(a)) for a in angles))
    return math.degrees(math.atan2(sum_y, sum_x)) % 360.0


def _ring_estimate(
    field: np.ndarray, center_x: float, center_y: float, radius: float,
) -> float:
    """单圈估计：该圈黄门内 S 剖面上楔内和最大的中线。

    Args:
        field: 黄门内 S（门外已置零）。
        center_x: 固定圆心 x。
        center_y: 固定圆心 y。
        radius: 采样半径。

    Returns:
        该圈估计的朝向。
    """
    height, width = field.shape[:2]
    count = int(round(360.0 / SECTOR_STEP_DEGREE))
    degs = np.arange(0.0, 360.0, SECTOR_STEP_DEGREE)
    radians = np.deg2rad(degs)
    cosines, sines = np.cos(radians), np.sin(radians)
    xs = np.clip(
        np.round(center_x + radius * cosines).astype(np.int32), 0, width - 1)
    ys = np.clip(
        np.round(center_y - radius * sines).astype(np.int32), 0, height - 1)
    profile = field[ys, xs].astype(np.float64)
    window = int(round(SECTOR_WEDGE_WIDTH / SECTOR_STEP_DEGREE))
    extended = np.concatenate([profile, profile[:window]])
    cumsum = np.cumsum(np.insert(extended, 0, 0.0))
    sums = cumsum[window:window + count] - cumsum[:count]
    index = int(np.argmax(sums))
    return float((index * SECTOR_STEP_DEGREE + SECTOR_WEDGE_WIDTH / 2) % 360.0)


def _sector_angle(
    rgb: MatLike, center_x: float, center_y: float,
) -> float | None:
    """先 H 滤黄、再 S 滑窗求镜头朝向，两圈起步、差异大加圈到稳定组。

    白天蓝底 S 高（r28 圈 60~150 度均值约 154），纯 S 滑窗被宽蓝底淹掉，
    指到 84~119 度；先过 H 14~34 黄门，蓝底直接拦掉，r23 回到 2.5 度。
    黄底上门约等于直通（扇形 24、黄底 21~23），退化成纯 S，之前 5 张的
    1.3 度还在。门内只看 S，不看 V：黄底 5 张上 V 门版有张偏 12 度。
    r28 北半截常被墙切掉、单圈往南偏（299.5），靠多圈投票纠回 2.5。

    Args:
        rgb: 小地图 RGB 图，正方形。
        center_x: 固定圆心 x。
        center_y: 圆心 y。

    Returns:
        镜头朝向角度；门内全空（小地图消失）时返回 None。
    """
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hue = hsv[:, :, 0].astype(np.float64)
    sat = hsv[:, :, 1].astype(np.float64)
    yellow = (hue >= SECTOR_YELLOW_H_MIN) & (hue <= SECTOR_YELLOW_H_MAX)
    field = np.where(yellow, sat, 0.0)
    if float(field.max()) <= 0.0:
        return None
    try:
        values: list[float] = []
        for radius in SECTOR_RING_ORDER:
            values.append(_ring_estimate(field, center_x, center_y, float(radius)))
            if len(values) == 2:
                if abs(_angle_delta(values[0], values[1])) <= SECTOR_TWO_DIFF:
                    return _circular_mean(values)
            elif len(values) >= 3:
                for cand in values:
                    members = [
                        v for v in values
                        if abs(_angle_delta(v, cand)) <= SECTOR_GROUP_DEGREE
                    ]
                    if len(members) >= 3:
                        return _circular_mean(members)
        if not values:
            return None
        return _circular_mean(values)
    except Exception:
        return None


def analyze(
    rgb: MatLike,
) -> tuple[float | None, float | None, float | None, float, tuple[float, float]]:
    """只算镜头朝向与固定圆心，不再检测菱形。

    圆心即角色位置，直接用几何中心。返回保持 5 元组，
    角色朝向两项恒为 None、半径恒为 0.0，调用方解包不用改。

    Args:
        rgb: 小地图 RGB 图，正方形。

    Returns:
        (None, None, 镜头朝向, 0.0, 圆心)。
        扫不到可信扇形时镜头朝向为 None。圆心为几何中心。
    """
    height, width = rgb.shape[:2]
    geo_x, geo_y = (width - 1) / 2, (height - 1) / 2
    center_x = geo_x + SECTOR_CENTER_OFFSET[0]
    center_y = geo_y + SECTOR_CENTER_OFFSET[1]
    center = (center_x, center_y)

    sector_value = _sector_angle(rgb, center_x, center_y)
    return None, None, sector_value, 0.0, center
