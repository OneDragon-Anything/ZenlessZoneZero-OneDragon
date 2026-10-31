"""贝果路线使用的地图模型：我们的独立分层底图。

坐标一律是「所属地图 + 分层名 + 全局画布坐标」。全局坐标 = 层内圆心 + 层偏移，
不再有 reference_spawn_pixel 那套以出生画面为原点的相对坐标。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from zzz_od.game_data.map_locator.map_locator import (
    MapLocator,
    default_layer_dir,
    load_map_locators,
)


@lru_cache(maxsize=1)
def _all_layers() -> tuple[MapLocator, ...]:
    """进程内只加载一次分层底图，各路线共用。"""
    return tuple(load_map_locators())


def layer_names() -> tuple[str, ...]:
    """返回全部可用分层名，形如 ``雅努斯幻境/Custom``。"""
    return tuple(layer.name for layer in _all_layers())


def all_layers() -> tuple[MapLocator, ...]:
    """返回全部独立层，供定位器使用。"""
    return _all_layers()


def find_layer_name(layer_name: str) -> MapLocator:
    """按完整分层名取层，不存在时报错。

    Args:
        layer_name: 含地图前缀的完整分层名。

    Returns:
        对应的层。

    Raises:
        ValueError: 分层名不在清单里。
    """
    return find_layer(layer_name)


def find_layer(layer_name: str) -> MapLocator:
    """按完整分层名取层。

    Args:
        layer_name: 含地图前缀的完整分层名。

    Returns:
        对应的层。

    Raises:
        ValueError: 分层名不在清单里。
    """
    for layer in _all_layers():
        if layer.name == layer_name:
            return layer
    raise ValueError(f'未知分层：{layer_name}')


@dataclass(frozen=True)
class BagelMapModel:
    """路线的展示与定位共用同一个分层。

    有效像素只表示该位置有底图纹理，不代表可通行，也不代表定位置信度。
    """

    layer_name: str
    locator: MapLocator
    rgba: np.ndarray
    coverage: np.ndarray
    origin: tuple[int, int]

    def contains(self, xy: tuple[float, float]) -> bool:
        """判断全局坐标是否落在该层有底图纹理的范围内。

        Args:
            xy: 全局画布坐标。

        Returns:
            落在有效像素上时为 True。
        """
        x, y = (round(xy[i] - self.origin[i]) for i in range(2))
        return (
            0 <= y < self.coverage.shape[0]
            and 0 <= x < self.coverage.shape[1]
            and self.coverage[y, x] > 0
        )

    def to_local(self, xy: tuple[float, float]) -> tuple[float, float]:
        """把全局坐标换成层内坐标，用于在底图上绘制。

        Args:
            xy: 全局画布坐标。

        Returns:
            相对该层左上角的坐标。
        """
        return (xy[0] - self.origin[0], xy[1] - self.origin[1])

    def to_global(self, xy: tuple[float, float]) -> tuple[float, float]:
        """把层内坐标换成全局坐标，用于保存路点。

        Args:
            xy: 相对该层左上角的坐标。

        Returns:
            全局画布坐标。
        """
        return (xy[0] + self.origin[0], xy[1] + self.origin[1])

    def reference_xy(self) -> tuple[float, float]:
        """取该层有效像素中距质心最近的一点，作为新建路点的参照。

        Returns:
            全局画布坐标。

        Raises:
            ValueError: 分层底图没有任何有效像素。
        """
        ys, xs = self.coverage.nonzero()
        if len(xs) == 0:
            raise ValueError(f'分层底图没有有效像素：{self.layer_name}')
        center_x, center_y = float(xs.mean()), float(ys.mean())
        nearest = int(np.argmin((xs - center_x) ** 2 + (ys - center_y) ** 2))
        return self.to_global((float(xs[nearest]), float(ys[nearest])))

    @classmethod
    def load(cls, layer_name: str) -> BagelMapModel:
        """加载指定分层作为路线底图。

        Args:
            layer_name: 含地图前缀的完整分层名。

        Returns:
            可直接用于展示与定位的地图模型。

        Raises:
            ValueError: 分层不存在或底图无法读取。
        """
        locator = find_layer(layer_name)
        rgba = cv2.imread(str(locator.image_path), cv2.IMREAD_UNCHANGED)
        if rgba is None or rgba.shape[2] != 4:
            raise ValueError(f'分层底图无法读取或不是 RGBA：{locator.image_path}')
        rgba = cv2.cvtColor(rgba, cv2.COLOR_BGRA2RGBA)
        rgba.setflags(write=False)
        coverage = (rgba[:, :, 3] > 128).astype(np.uint8)
        coverage.setflags(write=False)
        return cls(layer_name, locator, rgba, coverage, locator.origin)


def layer_image_path(layer_name: str) -> Path:
    """返回分层底图文件路径。

    Args:
        layer_name: 含地图前缀的完整分层名。

    Returns:
        底图文件路径。
    """
    return find_layer(layer_name).image_path


def map_dir() -> Path:
    """返回分层底图目录。"""
    return default_layer_dir()
