"""高危雅努斯局部小地图位置和角色箭头方向。"""

from math import atan2, degrees, hypot
from pathlib import Path

import cv2
import numpy as np
import yaml

from one_dragon.utils import os_utils
from zzz_od.application.bagel.bagel_minimap import register_minimap
from zzz_od.application.bagel.bagel_route import SUPPORTED_MAP_IDS, BagelRoute


class BagelRouteVision:
    """用已配准的局部参考帧返回第一张图上的坐标。"""

    def __init__(self, map_id: str = 'janus_high_a', route_data: BagelRoute | None = None) -> None:
        """按地图目录加载录像裁剪和已核验的局部坐标参数。"""
        if map_id not in SUPPORTED_MAP_IDS:
            raise ValueError(f'不支持的贝果路线: {map_id}')
        self.map_id: str = map_id
        root = Path(os_utils.get_resource_path('assets', 'game_data', 'bagel', map_id))
        with (root / 'route.yml').open(encoding='utf-8') as stream:
            route = yaml.safe_load(stream)
        self.route: BagelRoute = BagelRoute.from_dict(map_id, route_data.to_dict() if route_data else route, complete=route_data is None, check_roles=route_data is None)
        if self.route.map_id != map_id:
            raise ValueError('导航路线与参考图地图不一致')
        self.anchor: tuple[float, float] = tuple(route['anchor_xy'])
        self.spawn: tuple[float, float] = tuple(route['spawn_xy'])
        self.waypoints: list[tuple[str, tuple[float, float]]] = [
            (item.name, item.xy) for item in self.route.waypoints
        ]
        self.mask_settings: dict[str, object] = route['mask']
        self.arrow_settings: dict[str, object] = route['player_arrow']
        self.blur_size: int = route['registration_blur_size']
        self.references: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        self.min_channel_references: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        for item in route['references']:
            path = root / item['image']
            image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
            if image is None or image.shape != (201, 201, 3):
                raise ValueError(f'无效贝果参考图: {path}')
            mask = self._mask(image)
            transform = np.asarray(item['to_global'], dtype=np.float64)
            self.references.append((self._registration_image(image), mask, transform))
            self.min_channel_references.append((
                self._registration_image(image, use_min_channel=True), mask, transform,
            ))

    def _registration_image(self, crop: np.ndarray, *, use_min_channel: bool = False) -> np.ndarray:
        """平滑缩放纹理并均衡局部对比度；可用最小颜色通道抑制透出的彩色背景。"""
        gray = np.min(crop, axis=2) if use_min_channel else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)
        return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(blurred)

    def _mask(self, crop: np.ndarray) -> np.ndarray:
        """遮住外框、中心标记以及颜色过亮的动态层。"""
        settings = self.mask_settings
        center = tuple(settings['center_xy'])
        out = np.zeros(crop.shape[:2], np.uint8)
        cv2.circle(out, center, settings['outer_radius'], 255, -1)
        cv2.circle(out, center, settings['inner_radius'], 0, -1)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        out[(hsv[:, :, 1] > settings['maximum_saturation']) |
            (hsv[:, :, 2] < settings['minimum_brightness'])] = 0
        margin = int(settings.get('edge_margin', 0))
        if margin:
            # 描述子中心可能落在亮色道路旁的暗边，保留邻域但不扩大有效圆环。
            out = cv2.dilate(out, np.ones((margin * 2 + 1, margin * 2 + 1), np.uint8))
            ring = np.zeros_like(out)
            cv2.circle(ring, center, settings['outer_radius'], 255, -1)
            cv2.circle(ring, center, settings['inner_radius'], 0, -1)
            out = cv2.bitwise_and(out, ring)
        return out

    def locate(self, crop: np.ndarray) -> tuple[float, float] | None:
        """独立匹配每张参考帧；证据不足或任意两张冲突时不给位置。"""
        if crop.shape != (201, 201, 3) or crop.dtype != np.uint8:
            return None
        valid = self._mask(crop)
        current = self._registration_image(crop)
        candidates = self._match_references(current, valid, self.references)
        if not candidates:
            # 彩色背景仍可能淹没道路特征；仅在无匹配时换表示，不绕过参考图冲突。
            current = self._registration_image(crop, use_min_channel=True)
            candidates = self._match_references(current, valid, self.min_channel_references)
        if not candidates:
            return None
        for index, (_, first) in enumerate(candidates):
            for _, second in candidates[index + 1:]:
                if hypot(first[0] - second[0], first[1] - second[1]) > 5:
                    return None
        return max(candidates, key=lambda item: item[0])[1]

    def _match_references(
        self,
        current: np.ndarray,
        valid: np.ndarray,
        references: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
    ) -> list[tuple[int, tuple[float, float]]]:
        """用同一种预处理匹配所有参考图，返回通过原有几何校验的全局坐标。"""
        candidates: list[tuple[int, tuple[float, float]]] = []
        for image, ref_mask, transform in references:
            match = register_minimap(current, valid, image, ref_mask, self.anchor)
            if match is None:
                continue
            x, y = match.player_position
            global_xy = transform[:, :2] @ np.asarray((x, y)) + transform[:, 2]
            candidates.append((match.inliers, (float(global_xy[0]), float(global_xy[1]))))
        return candidates

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
        """返回命中的 map_id；多条同时命中时按声明顺序取前一个。"""
        for map_id in SUPPORTED_MAP_IDS:
            if self.routes[map_id].is_at_spawn(crop):
                return map_id
        return None

    def vision(self, map_id: str) -> BagelRouteVision:
        """取已加载的路线视觉。"""
        if map_id not in self.routes:
            raise ValueError(f'不支持的贝果路线: {map_id}')
        return self.routes[map_id]
