"""实时小地图到固定底图的独立定位，不持有游戏输入或上一帧位置。"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

import cv2
import numpy as np

from zzz_od.application.bagel.bagel_fixed_map import registration_image
from zzz_od.application.bagel.bagel_minimap import (
    extract_features,
    match_feature_regions,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from zzz_od.application.bagel.bagel_fixed_map import BagelFixedMap


@dataclass(frozen=True)
class MapLocation:
    """每帧定位诊断；失败不携带可供导航继续移动的坐标。"""

    position: tuple[float, float] | None
    map_snapshot_id: int
    reason: str
    representation: str
    inliers: int
    median_residual_px: float | None
    elapsed_ms: float


def minimap_mask(crop: np.ndarray, settings: Mapping[str, object]) -> np.ndarray:
    """沿用圆框、中心箭头和色偏背景的实时图遮罩。"""
    out = np.zeros(crop.shape[:2], np.uint8)
    center = tuple(settings['center_xy'])
    cv2.circle(out, center, settings['outer_radius'], 255, -1)
    cv2.circle(out, center, settings['inner_radius'], 0, -1)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    out[(hsv[:, :, 1] > settings['maximum_saturation']) | (hsv[:, :, 2] < settings['minimum_brightness'])] = 0
    margin = int(settings.get('edge_margin', 0))
    if margin:
        out = cv2.dilate(out, np.ones((margin * 2 + 1, margin * 2 + 1), np.uint8))
        ring = np.zeros_like(out)
        cv2.circle(ring, center, settings['outer_radius'], 255, -1)
        cv2.circle(ring, center, settings['inner_radius'], 0, -1)
        out = cv2.bitwise_and(out, ring)
    return out


def locate_on_map(snapshot: BagelFixedMap, crop: np.ndarray) -> MapLocation:
    """扫描全部空间分区；多个合格位置冲突时立即拒绝，不换表示绕过冲突。"""
    started = perf_counter()
    reason = 'insufficient_geometry'
    representation = ''
    if crop.shape != (201, 201, 3) or crop.dtype != np.uint8:
        reason = 'invalid_crop'
    else:
        valid = minimap_mask(crop, snapshot.mask_settings)
        for bank in snapshot.banks:
            representation = bank.representation
            current = extract_features(registration_image(crop, representation, snapshot.blur_size), valid)
            matches = match_feature_regions(current, bank.features, bank.regions, snapshot.anchor)
            if not matches:
                continue
            # 范围外的候选仍参与冲突检查，不能删掉竞争证据后挑一个位置。
            coordinates = np.asarray([match.player_position for match in matches])
            if np.linalg.norm(coordinates[:, None] - coordinates[None, :], axis=2).max() > 5:
                reason = 'ambiguous_position'
                break
            chosen = max(matches, key=lambda match: match.inliers)
            if not snapshot.supports_position(chosen.player_position):
                reason = 'outside_coverage'
                break
            position = tuple(chosen.player_position[i] + snapshot.origin[i] for i in range(2))
            return MapLocation(position, snapshot.snapshot_id, 'matched', representation, chosen.inliers, chosen.median_residual_px, (perf_counter() - started) * 1000)
    return MapLocation(None, snapshot.snapshot_id, reason, representation, 0, None, (perf_counter() - started) * 1000)
