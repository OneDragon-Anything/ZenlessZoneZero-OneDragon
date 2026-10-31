"""固定底图定位、路线匹配与实时角色朝向。

定位与朝向都来自我们的独立分层底图方案：
- 定位：高通纹理 + 归一化模板匹配，返回「层内圆心 + 层偏移」的全局坐标。
- 朝向：亮区菱形（角色）与环形扇形（镜头），正右为 0、逆时针增加。

路线匹配不用出生锚点：进局后先定位，再拿当前坐标和各路线第一个路点比距离，
取最近的一条；最近距离超过上限就认为不是已支持的路线。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from zzz_od.application.bagel.bagel_map_model import (
    BagelMapModel,
    all_layers,
    find_layer,
)
from zzz_od.application.bagel.bagel_route import (
    ROUTE_LABELS,
    SUPPORTED_ROUTE_IDS,
    route_layer,
)
from zzz_od.game_data.map_locator.map_locator import MultiMapLocator
from zzz_od.game_data.map_locator.minimap_angle import analyze

if TYPE_CHECKING:
    from zzz_od.application.bagel.bagel_flow import BagelFlow
    from zzz_od.application.bagel.bagel_route import BagelRoute

ROUTE_MATCH_MAX_DISTANCE: float = 100.0
"""当前坐标与路线起点的最大距离。超过它就不算命中任何路线。"""


def route_start(flow: BagelFlow) -> tuple[float, float] | None:
    """取流程起点的全局坐标。

    Args:
        flow: 已校验的流程。

    Returns:
        第一个路点的坐标；流程里没有任何路点时返回 None。
    """
    for step in flow.steps:
        if step.waypoints:
            return step.waypoints[0].xy
    return None


class BagelRouteVision:
    """正式导航和开发试跑共用一份分层底图与定位状态。"""

    def __init__(
        self,
        layer_name: str,
        route_data: BagelRoute | None = None,
        map_model: BagelMapModel | None = None,
    ) -> None:
        """
        Args:
            layer_name: 路线所在分层，含地图前缀。
            route_data: 已有路线，缺省时只按分层加载。
            map_model: 已加载的地图模型，缺省时按分层名加载。

        Raises:
            ValueError: 传入的地图模型与分层名不一致。
        """
        self.layer_name: str = layer_name
        self.map: BagelMapModel = (
            map_model if map_model is not None else BagelMapModel.load(layer_name)
        )
        if self.map.layer_name != layer_name:
            raise ValueError('导航路线与分层底图不一致')
        self.locator: MultiMapLocator = MultiMapLocator(list(all_layers()))
        self.route: BagelRoute | None = route_data
        self.last_position: tuple[float, float] | None = None
        self.last_score: float = 0.0
        self.last_layer_name: str | None = None

    def locate(self, crop: np.ndarray) -> tuple[float, float] | None:
        """返回全局坐标或明确失败。

        Args:
            crop: 小地图裁剪，BGR 或 RGB 均可。

        Returns:
            全局画布坐标，无法定位时返回 None。
        """
        result = self.locator.locate(_rgb(crop))
        if result is None:
            self.last_position = None
            self.last_score = 0.0
            self.last_layer_name = None
            return None
        locator, score, center = result
        self.last_score = score
        self.last_layer_name = locator.name
        self.last_position = (float(center[0]), float(center[1]))
        return self.last_position

    def player_angle(self, crop: np.ndarray) -> float | None:
        """返回角色朝向角，正右为 0、逆时针增加。

        这个值可直接与 ``atan2(target_y - position_y, target_x - position_x)``
        得到的目标方向比较，不需要再取负。

        Args:
            crop: 小地图裁剪，BGR 或 RGB 均可。

        Returns:
            角色朝向角度，识别不出时返回 None。
        """
        _marker_vertices, marker_edges, _sector, _radius, _center = analyze(_rgb(crop))
        return marker_edges

    def camera_angle(self, crop: np.ndarray) -> float | None:
        """返回镜头朝向角，正右为 0、逆时针增加。

        Args:
            crop: 小地图裁剪，BGR 或 RGB 均可。

        Returns:
            镜头朝向角度，识别不出时返回 None。
        """
        _marker_vertices, _marker_edges, sector, _radius, _center = analyze(_rgb(crop))
        return sector


def _rgb(crop: np.ndarray) -> np.ndarray:
    """统一成 RGB，定位与朝向都按 RGB 计算。

    Args:
        crop: 小地图裁剪，BGR 或 RGB 均可，也接受单通道。

    Returns:
        RGB 数组；单通道输入原样返回。
    """
    return crop if crop.ndim == 2 else crop[:, :, ::-1]


@dataclass(frozen=True)
class RouteEntry:
    """参与匹配的一条路线：所属地图、分层与起点坐标。"""

    route_id: str
    layer_name: str
    map_id: str
    start: tuple[float, float]


class BagelRouteMatcher:
    """按与路线起点的距离选一条路线，最近都超过上限则拒绝。

    起点就是该路线第一个路点，所以录完路线即可参与匹配，不需要另外标定出生点。
    不同地图的全局坐标会互相重叠，所以只比较与当前所在层同属一张地图的路线。
    """

    def __init__(
        self,
        flows: dict[str, BagelFlow] | None = None,
        max_distance: float = ROUTE_MATCH_MAX_DISTANCE,
    ) -> None:
        """
        Args:
            flows: 各路线已保存的流程，键为路线标识；缺省时读正式流程。
            max_distance: 命中某条路线允许的最大距离。

        Raises:
            ValueError: 某条路线还没有路点，无法确定起点。
        """
        from zzz_od.application.bagel.bagel_flow import load_published_flow

        self.max_distance: float = max_distance
        data = flows if flows is not None else {
            key: load_published_flow(key) for key in SUPPORTED_ROUTE_IDS
        }
        self.entries: list[RouteEntry] = []
        self.visions: dict[str, BagelRouteVision] = {}
        for route_id in SUPPORTED_ROUTE_IDS:
            flow = data.get(route_id)
            if flow is None:
                raise ValueError(f'缺少路线的发布流程：{route_id}')
            start = route_start(flow)
            if start is None:
                raise ValueError(
                    f'{ROUTE_LABELS[route_id]} 还没有录入路点，无法按起点匹配'
                )
            layer_name = route_layer(route_id)
            self.entries.append(
                RouteEntry(route_id, layer_name, find_layer(layer_name).map_id, start)
            )
            self.visions[route_id] = BagelRouteVision(layer_name)
        self.locator: MultiMapLocator = MultiMapLocator(list(all_layers()))
        self.last_position: tuple[float, float] | None = None
        self.last_map_id: str | None = None

    def locate(self, crop: np.ndarray) -> tuple[float, float] | None:
        """在当前画面定位一次，同时记下所在层与所属地图。

        Args:
            crop: 小地图裁剪。

        Returns:
            全局画布坐标，无法定位时返回 None。
        """
        result = self.locator.locate(_rgb(crop))
        if result is None:
            self.last_position = None
            self.last_map_id = None
            return None
        locator, _score, center = result
        self.last_position = (float(center[0]), float(center[1]))
        self.last_map_id = locator.map_id
        return self.last_position

    def match(self, crop: np.ndarray) -> str | None:
        """返回命中的路线标识；超出距离上限或无法定位时返回 None。

        Args:
            crop: 小地图裁剪。

        Returns:
            路线标识。
        """
        position = self.locate(crop)
        if position is None or self.last_map_id is None:
            return None
        nearest: tuple[float, str] | None = None
        for entry in self.entries:
            if entry.map_id != self.last_map_id:
                continue
            distance = math.dist(position, entry.start)
            if nearest is None or distance < nearest[0]:
                nearest = (distance, entry.route_id)
        if nearest is None or nearest[0] > self.max_distance:
            return None
        return nearest[1]

    def vision(self, route_id: str) -> BagelRouteVision:
        """取已加载的路线视觉。

        Args:
            route_id: 路线标识。

        Returns:
            该路线的视觉对象。

        Raises:
            ValueError: 路线标识不受支持。
        """
        if route_id not in self.visions:
            raise ValueError(f'不支持的贝果路线: {route_id}')
        return self.visions[route_id]
