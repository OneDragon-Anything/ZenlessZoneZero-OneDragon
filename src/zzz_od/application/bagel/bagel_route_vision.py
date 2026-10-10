"""固定底图定位、出生识别与实时角色箭头方向。"""

from __future__ import annotations

from math import atan2, degrees, hypot
from typing import TYPE_CHECKING

import cv2
import numpy as np

from zzz_od.application.bagel.bagel_fixed_map import load_fixed_map
from zzz_od.application.bagel.bagel_flow import load_published_flow
from zzz_od.application.bagel.bagel_map_locator import locate_on_map
from zzz_od.application.bagel.bagel_route import SUPPORTED_MAP_IDS, BagelRoute

if TYPE_CHECKING:
    from collections.abc import Mapping

    from zzz_od.application.bagel.bagel_fixed_map import BagelFixedMap
    from zzz_od.application.bagel.bagel_map_locator import MapLocation


class BagelRouteVision:
    """出生识别、正式导航和开发试跑共用一份固定地图快照。"""

    def __init__(
        self,
        map_id: str = 'janus_high_a',
        route_data: BagelRoute | None = None,
        map_snapshot: BagelFixedMap | None = None,
    ) -> None:
        """独立加载或接收本次执行的地图，正式路点仅来自发布流程。"""
        self.map_id: str = map_id
        self.map: BagelFixedMap = map_snapshot if map_snapshot is not None else load_fixed_map(map_id)
        if self.map.map_id != map_id:
            raise ValueError('导航路线与固定地图不一致')
        if route_data is None:
            points = dict.fromkeys(point for step in load_published_flow(map_id).steps for point in step.waypoints)
            self.route: BagelRoute = BagelRoute(map_id, tuple(points))
        else:
            self.route = BagelRoute.from_dict(map_id, route_data.to_dict(), complete=False, check_roles=False)
        self.anchor: tuple[float, float] = self.map.anchor
        self.spawn: tuple[float, float] = self.map.spawn
        self.arrow_settings: Mapping[str, object] = self.map.arrow_settings
        self.last_location: MapLocation | None = None

    def locate(self, crop: np.ndarray) -> tuple[float, float] | None:
        """返回原路线坐标或明确失败，并保存本帧诊断。"""
        self.last_location = locate_on_map(self.map, crop)
        return self.last_location.position

    def player_angle(self, crop: np.ndarray) -> float | None:
        """读取黄色箭头亮色尖端的方向；图像右方为零、顺时针为正。"""
        if crop.shape != (201, 201, 3) or crop.dtype != np.uint8:
            return None
        settings = self.arrow_settings
        radius = settings['crop_radius']
        ax, ay = (int(value) for value in self.anchor)
        arrow = crop[ay - radius:ay + radius + 1, ax - radius:ax + radius + 1]
        hsv = cv2.cvtColor(arrow, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(settings['hsv_lower']), np.array(settings['hsv_upper']))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: list[np.ndarray] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if not settings['area_range'][0] <= area <= settings['area_range'][1]:
                continue
            x, y, width, height = cv2.boundingRect(contour)
            if x == 0 or y == 0 or x + width == mask.shape[1] or y + height == mask.shape[0]:
                continue
            moments = cv2.moments(contour)
            if hypot(moments['m10'] / area - radius, moments['m01'] / area - radius) <= settings['maximum_center_offset']:
                candidates.append(contour)
        if len(candidates) != 1:
            return None
        mask[:] = 0
        cv2.drawContours(mask, candidates, -1, 255, -1)
        ys, xs = np.nonzero(mask)
        green = arrow[:, :, 1]
        if np.ptp(green[mask > 0]) < settings['minimum_green_spread']:
            return None
        threshold = np.percentile(green[mask > 0], settings['tip_percentile'])
        tip_y, tip_x = np.nonzero((mask > 0) & (green >= threshold))
        dx, dy = float(tip_x.mean() - xs.mean()), float(tip_y.mean() - ys.mean())
        if hypot(dx, dy) < settings['minimum_tip_offset']:
            return None
        return degrees(atan2(dy, dx)) % 360

    def is_at_spawn(self, crop: np.ndarray) -> bool:
        """位置靠近本路线出生点才识别为该路线。"""
        position = self.locate(crop)
        return position is not None and hypot(position[0] - self.spawn[0], position[1] - self.spawn[1]) <= 5


class BagelSpawnMatcher:
    """在已支持的出生路线中选一条，未知则返回 None。"""

    def __init__(self, routes: dict[str, BagelRoute] | None = None) -> None:
        """预加载全部支持路线，避免每局反复读盘。"""
        self.routes: dict[str, BagelRouteVision] = {
            map_id: BagelRouteVision(map_id, (routes or {}).get(map_id)) for map_id in SUPPORTED_MAP_IDS
        }

    def match(self, crop: np.ndarray) -> str | None:
        """返回命中的 map_id；多条同时命中则拒绝。"""
        matches = [map_id for map_id in SUPPORTED_MAP_IDS if self.routes[map_id].is_at_spawn(crop)]
        return matches[0] if len(matches) == 1 else None

    def vision(self, map_id: str) -> BagelRouteVision:
        """取已加载的路线视觉。"""
        if map_id not in self.routes:
            raise ValueError(f'不支持的贝果路线: {map_id}')
        return self.routes[map_id]
