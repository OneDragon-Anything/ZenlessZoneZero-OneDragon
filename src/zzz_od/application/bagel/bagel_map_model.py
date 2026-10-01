"""展示与定位共用发布底图，保留未知区域。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np

from zzz_od.application.bagel.bagel_fixed_map import load_fixed_map

if TYPE_CHECKING:
    from zzz_od.application.bagel.bagel_fixed_map import BagelFixedMap


@dataclass(frozen=True)
class BagelMapModel:
    """发布底图与原坐标偏移；有效像素不表示通行能力或定位置信度。"""

    map_id: str
    snapshot: BagelFixedMap
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
        """读取与定位完全相同的已校验底图，不在打开编辑器时制图。"""
        snapshot = load_fixed_map(map_id)
        rgba = cv2.cvtColor(snapshot.image, cv2.COLOR_BGRA2RGBA)
        rgba.setflags(write=False)
        return cls(
            map_id, snapshot, rgba, snapshot.mask, snapshot.origin, snapshot.spawn,
            snapshot.reference_centers, snapshot.landmarks,
        )
