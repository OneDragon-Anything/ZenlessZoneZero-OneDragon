"""按独立分层底图定位小地图，返回所属地图统一画布上的像素坐标。

每层底图各自记录在所属地图原画布上的偏移：层内匹配出圆心后加偏移，
得到跨层可比的全局坐标。不把楼层压平成一张底图。

本模块是插件 plugins/map_overlay 定位算法的独立移植，两边不共享代码。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np
from cv2.typing import MatLike
from PIL import Image

MINIMAP_INNER_RADIUS = 88
"""小地图圆形有效区半径。圆外只可能是 UI 装饰，不参与匹配。"""

TEXTURE_PAD = 110
"""底图四周补齐量。贴边位置也要能容纳完整的 200×200 搜索窗口。"""

TEXTURE_HP_KERNEL = 15
"""高通核尺寸，用于压掉大面积明暗过渡、只留纹理。"""

MINIMAP_MIN_TEXTURE = 200.0
"""小地图纹理能量下限。低于此值认为是空白或全遮挡帧。"""

ACCEPT_SCORE = 0.18
"""当前层继续命中的分数门槛。"""

CROSS_MAP_SCORE = 0.22
"""切换到其它层所需的分数门槛，比留在当前层更严格。"""

NEAR_RADIUS = 10
"""追踪时在上一帧圆心附近搜索的半径。"""

LONG_MISS_SECONDS = 1.0
"""连续丢失超过此时长后放开全部层搜索。"""

MIN_WINDOW_ENERGY = 1e-4
"""底图窗口方差下限。零方差窗口会返回有限的 1.0 假高分。"""


def high_pass(gray: MatLike, kernel: int = TEXTURE_HP_KERNEL) -> MatLike:
    """灰度减高斯模糊，提取纹理。

    Args:
        gray: 单通道灰度图。
        kernel: 高斯核尺寸。

    Returns:
        与输入同尺寸的纹理图。
    """
    return gray - cv2.GaussianBlur(gray, (kernel, kernel), 0)


def minimap_texture(rgb: MatLike) -> tuple[MatLike, MatLike]:
    """提取小地图纹理，圆外清零；不使用颜色或朝向约束。

    Args:
        rgb: 小地图 RGB 图，正方形。

    Returns:
        (纹理图, 有效区掩码)。
    """
    height, width = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    valid = np.zeros((height, width), np.float32)
    cv2.circle(valid, (width // 2, height // 2), MINIMAP_INNER_RADIUS, 1.0, -1)
    return high_pass(gray) * valid, valid


def base_texture(rgba: MatLike) -> MatLike:
    """透明区填黑后提取底图纹理。

    Args:
        rgba: 底图 RGBA 数组。

    Returns:
        单通道纹理图。
    """
    rgb = rgba[:, :, :3].astype(np.float32)
    solid = (rgba[:, :, 3] > 128).astype(np.float32)
    gray = cv2.cvtColor(
        np.clip(rgb * solid[:, :, None], 0, 255).astype(np.uint8),
        cv2.COLOR_RGB2GRAY,
    ).astype(np.float32)
    return high_pass(gray)


class MapLocator:
    """单层底图；纹理与积分图只计算一次，搜索结果加偏移返回全局坐标。"""

    def __init__(
        self,
        name: str,
        image_path: Path,
        origin: tuple[int, int] = (0, 0),
        map_id: str | None = None,
    ) -> None:
        """
        Args:
            name: 完整分层名，含地图前缀，如 ``雅努斯幻境/Custom``。
            image_path: 该层底图路径。
            origin: 该层在所属地图原画布上的偏移。
            map_id: 所属地图标识，缺省取 ``name``。
        """
        self.name: str = name
        self.image_path: Path = image_path
        self.origin: tuple[int, int] = origin
        self.map_id: str = name if map_id is None else map_id
        rgba = np.array(Image.open(image_path).convert('RGBA'))
        self.width: int = int(rgba.shape[1])
        self.height: int = int(rgba.shape[0])
        self._pad: int = TEXTURE_PAD
        self._texture: MatLike = np.pad(
            base_texture(rgba), ((self._pad, self._pad), (self._pad, self._pad)),
        )
        self._sum: MatLike
        self._squared_sum: MatLike
        self._sum, self._squared_sum = cv2.integral2(
            self._texture, sdepth=cv2.CV_64F, sqdepth=cv2.CV_64F,
        )

    def intersects(self, center: tuple[int, int], radius: int) -> bool:
        """判断圆形视窗是否与本层画布相交，坐标均为地图全局坐标。

        Args:
            center: 视窗圆心的全局坐标。
            radius: 视窗半径。

        Returns:
            相交时为 True。
        """
        left, top = self.origin
        nearest_x = min(max(center[0], left), left + self.width - 1)
        nearest_y = min(max(center[1], top), top + self.height - 1)
        return (center[0] - nearest_x) ** 2 + (center[1] - nearest_y) ** 2 <= radius ** 2

    def locate(
        self,
        minimap_rgb: MatLike,
        last_center: tuple[int, int] | None = None,
        radius: int | None = None,
    ) -> tuple[float, tuple[int, int]] | None:
        """在本层搜索，last_center 和返回坐标均包含地图偏移。

        Args:
            minimap_rgb: 小地图 RGB 图。
            last_center: 上一帧圆心，给定时只在其附近搜索。
            radius: 局部搜索半径，配合 last_center 使用。

        Returns:
            (评分, 全局坐标圆心)，无法匹配时返回 None。
        """
        texture, _ = minimap_texture(minimap_rgb)
        return self.search_with_texture(texture, last_center, radius)

    def search_with_texture(
        self,
        texture: MatLike,
        last_center: tuple[int, int] | None = None,
        radius: int | None = None,
    ) -> tuple[float, tuple[int, int]] | None:
        """使用共用的小地图模板搜索，拒绝零方差窗口和非有限评分。

        Args:
            texture: 已提取的小地图纹理。
            last_center: 上一帧圆心，给定时只在其附近搜索。
            radius: 局部搜索半径。

        Returns:
            (评分, 全局坐标圆心)，无法匹配时返回 None。
        """
        if float(np.abs(texture).sum()) < MINIMAP_MIN_TEXTURE:
            return None
        height, width = texture.shape[:2]
        x1, y1 = 0, 0
        y2, x2 = self._texture.shape[:2]
        if last_center is not None and radius is not None:
            local_x = last_center[0] - self.origin[0] + self._pad
            local_y = last_center[1] - self.origin[1] + self._pad
            x1 = max(0, local_x - width // 2 - radius)
            y1 = max(0, local_y - height // 2 - radius)
            x2 = min(x2, local_x - width // 2 + radius + width)
            y2 = min(y2, local_y - height // 2 + radius + height)
        if x2 - x1 < width or y2 - y1 < height:
            return None

        sums = self._sum[y1:y2 + 1, x1:x2 + 1]
        squares = self._squared_sum[y1:y2 + 1, x1:x2 + 1]
        window_sum = (
            sums[height:, width:] - sums[:-height, width:]
            - sums[height:, :-width] + sums[:-height, :-width]
        )
        energy = (
            squares[height:, width:] - squares[:-height, width:]
            - squares[height:, :-width] + squares[:-height, :-width]
            - window_sum * window_sum / (height * width)
        )
        valid = energy > MIN_WINDOW_ENERGY
        if not valid.any():
            return None
        response = cv2.matchTemplate(
            self._texture[y1:y2, x1:x2], texture, cv2.TM_CCOEFF_NORMED,
        )
        response[~valid | ~np.isfinite(response)] = -np.inf
        _, score, _, point = cv2.minMaxLoc(response)
        if not np.isfinite(score):
            return None
        center = (
            point[0] + x1 + width // 2 - self._pad + self.origin[0],
            point[1] + y1 + height // 2 - self._pad + self.origin[1],
        )
        return float(score), center


class MultiMapLocator:
    """未定位时搜全部层，成功后追踪当前层，丢失时逐步放开搜索。"""

    def __init__(self, locators: list[MapLocator], near_radius: int = NEAR_RADIUS) -> None:
        """
        Args:
            locators: 全部独立层，顺序即搜索顺序。
            near_radius: 追踪时在上一帧圆心附近搜索的半径。

        Raises:
            ValueError: 没有传入任何层。
        """
        if not locators:
            raise ValueError('至少要有一张底版')
        self.locators: list[MapLocator] = locators
        self.near_radius: int = near_radius
        self._current: int | None = None
        self._last_center: tuple[int, int] | None = None
        self._last_hit_time: float = 0.0

    @property
    def current(self) -> MapLocator | None:
        """当前命中的独立层。"""
        return None if self._current is None else self.locators[self._current]

    def locate(self, minimap_rgb: MatLike) -> tuple[MapLocator, float, tuple[int, int]] | None:
        """当前层失败后，先比较同地图附近各层，丢失满一秒再搜索全部层。

        Args:
            minimap_rgb: 小地图 RGB 图。

        Returns:
            (命中的层, 评分, 全局坐标圆心)，无法定位时返回 None。
        """
        texture, _ = minimap_texture(minimap_rgb)
        if float(np.abs(texture).sum()) < MINIMAP_MIN_TEXTURE:
            return None
        current = self._current
        reference = self._last_center
        if current is not None and reference is not None:
            hit = self.locators[current].search_with_texture(texture, reference, self.near_radius)
            if hit is not None and hit[0] >= ACCEPT_SCORE:
                return self._accept(current, hit)
            if time.monotonic() - self._last_hit_time < LONG_MISS_SECONDS:
                indices = [
                    index for index, locator in enumerate(self.locators)
                    if index != current
                    and locator.map_id == self.locators[current].map_id
                    and locator.intersects(reference, MINIMAP_INNER_RADIUS + self.near_radius)
                ]
                best = self._search(indices, texture, reference, self.near_radius)
                return None if best is None else self._accept(best[0], (best[1], best[2]))

        best = self._search(list(range(len(self.locators))), texture, None, None)
        return None if best is None else self._accept(best[0], (best[1], best[2]))

    def _search(
        self,
        indices: list[int],
        texture: MatLike,
        reference: tuple[int, int] | None,
        radius: int | None,
    ) -> tuple[int, float, tuple[int, int]] | None:
        """比较本帧有效候选，不用历史最高分阻挡换层。"""
        best: tuple[int, float, tuple[int, int]] | None = None
        for index in indices:
            hit = self.locators[index].search_with_texture(texture, reference, radius)
            threshold = ACCEPT_SCORE if index == self._current else CROSS_MAP_SCORE
            if hit is None or hit[0] < threshold:
                continue
            if best is None or hit[0] > best[1]:
                best = (index, hit[0], hit[1])
        return best

    def _accept(
        self, index: int, hit: tuple[float, tuple[int, int]],
    ) -> tuple[MapLocator, float, tuple[int, int]]:
        self._current = index
        self._last_center = hit[1]
        self._last_hit_time = time.monotonic()
        return self.locators[index], hit[0], hit[1]


def default_layer_dir() -> Path:
    """返回主仓分层底图目录。

    Returns:
        含 ``layers.json`` 与各层图片的目录路径。
    """
    from one_dragon.utils import os_utils

    return Path(os_utils.get_resource_path('assets', 'game_data', 'map_locator'))


def load_map_locators(map_dir: Path | None = None) -> list[MapLocator]:
    """按独立层清单加载图像及其在所属地图上的偏移。

    Args:
        map_dir: 分层底图目录，缺省用主仓资源目录。

    Returns:
        按清单顺序排列的层列表。
    """
    directory = default_layer_dir() if map_dir is None else map_dir
    data = json.loads((directory / 'layers.json').read_text(encoding='utf-8'))
    return [
        MapLocator(
            name=f"{layer['map_id']}/{layer['name']}",
            image_path=directory / layer['image'],
            origin=tuple(layer['origin']),
            map_id=layer['map_id'],
        )
        for layer in data['layers']
    ]
