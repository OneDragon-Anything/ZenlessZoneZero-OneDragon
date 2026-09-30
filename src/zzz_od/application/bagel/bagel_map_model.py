"""将两个出生地各自的参考图投影到出生像素坐标，保留未知区域。"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import yaml

from zzz_od.application.bagel.bagel_route import resource_root


@dataclass(frozen=True)
class BagelMapModel:
    """局部拼接图与原坐标偏移；覆盖数不表示通行能力或定位置信度。"""

    map_id: str
    rgba: np.ndarray
    coverage: np.ndarray
    origin: tuple[int, int]
    spawn: tuple[float, float]
    reference_centers: tuple[tuple[str, tuple[float, float]], ...]
    landmarks: tuple[tuple[str, tuple[float, float]], ...]

    def contains(self, xy: tuple[float, float]) -> bool:
        """是否落在至少一张参考图的可展示区域内。"""
        x, y = (round(xy[i] - self.origin[i]) for i in range(2))
        return 0 <= y < self.coverage.shape[0] and 0 <= x < self.coverage.shape[1] and self.coverage[y, x] > 0

    @classmethod
    def load(cls, map_id: str) -> BagelMapModel:
        """矩阵与定位共享资源；不按出生地名字猜测游戏全局坐标。"""
        root = resource_root(map_id)
        data = yaml.safe_load((root / 'route.yml').read_text(encoding='utf-8'))
        corners = np.asarray([[0, 0], [200, 0], [200, 200], [0, 200]], dtype=float)
        anchor = np.asarray(data['anchor_xy'], dtype=float)
        frames: list[tuple[str, np.ndarray, np.ndarray]] = []
        bounds: list[np.ndarray] = []
        centers: list[tuple[str, tuple[float, float]]] = []
        for entry in data['references']:
            image = cv2.imdecode(np.fromfile(root / entry['image'], np.uint8), cv2.IMREAD_COLOR)
            matrix = np.asarray(entry['to_global'], dtype=float)
            if image is None or image.shape != (201, 201, 3) or matrix.shape != (2, 3) or not np.isfinite(matrix).all():
                raise ValueError(f'小地图参考图或矩阵无效：{entry["image"]}')
            bounds.append(corners @ matrix[:, :2].T + matrix[:, 2])
            center = matrix[:, :2] @ anchor + matrix[:, 2]
            centers.append((entry['image'], (float(center[0]), float(center[1]))))
            frames.append((entry['image'], image, matrix))
        all_bounds = np.concatenate(bounds)
        origin = np.floor(all_bounds.min(axis=0)).astype(int)
        width, height = (np.ceil(all_bounds.max(axis=0)).astype(int) - origin + 1).tolist()
        total = np.zeros((height, width, 3), dtype=np.float32)
        weight = np.zeros((height, width), dtype=np.float32)
        coverage = np.zeros((height, width), dtype=np.uint8)
        for _name, image, matrix in frames:
            mask = np.zeros((201, 201), dtype=np.uint8)
            center = tuple(int(v) for v in anchor)
            cv2.circle(mask, center, data['mask']['outer_radius'], 255, -1)
            cv2.circle(mask, center, data['mask']['inner_radius'], 0, -1)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            mask[hsv[:, :, 1] > data['mask']['maximum_saturation']] = 0
            transform = matrix.copy()
            transform[:, 2] -= origin
            warped_mask = cv2.warpAffine(mask, transform, (width, height), flags=cv2.INTER_NEAREST)
            warped = cv2.warpAffine(image, transform, (width, height))
            valid = warped_mask > 0
            total[valid] += warped[valid]
            weight[valid] += 1
            coverage[valid] += 1
        result = np.zeros((height, width, 4), dtype=np.uint8)
        valid = weight > 0
        result[valid, :3] = (total[valid] / weight[valid, None]).astype(np.uint8)[:, ::-1]
        result[valid, 3] = 255
        landmarks = tuple((item['name'], tuple(item['xy'])) for item in data.get('landmarks', []))
        return cls(map_id, result, coverage, (int(origin[0]), int(origin[1])), tuple(data['spawn_xy']), tuple(centers), landmarks)
