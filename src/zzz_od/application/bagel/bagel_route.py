"""编辑器和导航共同使用的路线模型；坐标属于各出生参考图。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from one_dragon.utils import os_utils

SUPPORTED_MAP_IDS: tuple[str, ...] = ('janus_high_a', 'janus_high_b', 'janus_high_c')
MAP_LABELS: dict[str, str] = {
    'janus_high_a': 'A · 录像店', 'janus_high_b': 'B · 白鸽工地地铁站',
    'janus_high_c': 'C · 单廊双容器',
}
ROLE_LABELS: dict[str, str] = {
    'turn': '转折', 'entry': '保险箱入口', 'approach': '接近', 'target': '交互目标',
}


def resource_root(map_id: str) -> Path:
    """只允许已支持的资源目录。"""
    if map_id not in SUPPORTED_MAP_IDS:
        raise ValueError(f'不支持的贝果路线：{map_id}')
    return Path(os_utils.get_resource_path('assets', 'game_data', 'bagel', map_id))


def _number(value: object, label: str, lower: float, upper: float) -> float:
    """拒绝布尔、非有限值和越界值。"""
    if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f'{label} 必须是 {lower} 至 {upper} 的有限数值')
    return float(value)


@dataclass(frozen=True)
class BagelWaypoint:
    """路点用途与路段独立于显示名称，避免改名改变执行语义。"""

    name: str
    xy: tuple[float, float]
    stage: str
    role: str
    tolerance: float | None = None
    stop: bool = True
    passed_tolerance: float | None = None

    @property
    def arrival_radius(self) -> float:
        """显示与执行共用到达半径，未覆盖时沿用原导航规则。"""
        if self.tolerance is not None:
            return self.tolerance
        if self.stage == 'move':
            return 2
        if self.stage == 'safe':
            from zzz_od.application.bagel.bagel_const import (
                NAV_SAFE_APPROACH_DISTANCE,
                NAV_SAFE_CORNER_DISTANCE,
            )

            return NAV_SAFE_CORNER_DISTANCE if self.role == 'entry' else NAV_SAFE_APPROACH_DISTANCE
        return 2 if self.role == 'target' else 1

    @property
    def passed_radius(self) -> float:
        """转折落在身后时允许切段的距离，覆盖容差时也同步收紧。"""
        if self.passed_tolerance is not None:
            return self.passed_tolerance
        if self.stage == 'move':
            return self.arrival_radius
        if self.tolerance is not None:
            return self.tolerance
        return self.arrival_radius if self.stage == 'safe' else 3

    def to_dict(self) -> dict[str, Any]:
        """生成 YAML 可写的路点数据。"""
        data = {'name': self.name, 'xy': list(self.xy), 'stage': self.stage, 'role': self.role, 'stop': self.stop}
        if self.tolerance is not None:
            data['tolerance'] = self.tolerance
        if self.passed_tolerance is not None:
            data['passed_tolerance'] = self.passed_tolerance
        return data


@dataclass(frozen=True)
class BagelRoute:
    """一次导航使用不可变快照，编辑草稿不会改变正在运行的路线。"""

    map_id: str
    waypoints: tuple[BagelWaypoint, ...]

    def points_for(self, stage: str) -> tuple[BagelWaypoint, ...]:
        """按明确路段取点，不检查中文名字。"""
        return tuple(point for point in self.waypoints if point.stage == stage)

    def to_dict(self) -> dict[str, Any]:
        """生成当前导航路点的数据。"""
        return {
            'map_id': self.map_id, 'waypoints': [p.to_dict() for p in self.waypoints],
        }

    @classmethod
    def from_dict(cls, map_id: str, data: dict[str, Any], *, complete: bool = True, check_roles: bool = True) -> BagelRoute:
        """在任何游戏输入前校验持久化数据或编辑草稿。"""
        if map_id not in SUPPORTED_MAP_IDS or not isinstance(data, dict) or data.get('map_id') != map_id:
            raise ValueError('路线地图标识不匹配')
        values = data.get('waypoints')
        if not isinstance(values, list) or len(values) > 100:
            raise ValueError('路点必须是至多 100 项的列表')
        points: list[BagelWaypoint] = []
        for value in values:
            if not isinstance(value, dict) or set(value) - {'name', 'xy', 'stage', 'role', 'tolerance', 'stop', 'passed_tolerance'}:
                raise ValueError('路点格式或字段无效')
            name, xy = value.get('name'), value.get('xy')
            stage, role = value.get('stage'), value.get('role')
            if not isinstance(name, str) or not name.strip() or len(name) > 60:
                raise ValueError('路点名称须为 1 至 60 个字符')
            stages = ('box', 'safe', 'mech', 'move') if not complete and not check_roles else ('box', 'safe', 'mech')
            if stage not in stages or not isinstance(role, str) or role not in ROLE_LABELS:
                raise ValueError('路点缺少有效路段或用途')
            if not isinstance(xy, (list, tuple)) or len(xy) != 2:
                raise ValueError('路点坐标必须有 X、Y 两项')
            tolerance = value.get('tolerance')
            if tolerance is not None:
                tolerance = _number(tolerance, '到达容差', 0.1, 30)
            passed = value.get('passed_tolerance')
            if passed is not None:
                passed = _number(passed, '越点容差', 0.1, 30)
                if complete or check_roles:
                    raise ValueError('只有普通移动可以单独设置越点范围')
            stop = value.get('stop', True)
            if not isinstance(stop, bool):
                raise ValueError('停步要求必须是布尔值')
            point = BagelWaypoint(name.strip(), tuple(_number(v, '坐标', -1000, 1000) for v in xy), stage, role, tolerance, stop, passed)
            points.append(point)
        route = cls(map_id, tuple(points))
        box, safe, mech = (
            route.points_for('box'), route.points_for('safe'), route.points_for('mech'),
        )
        if any(p.stage == 'move' for p in points) and (box or safe or mech):
            raise ValueError('独立坐标移动不能混入容器路段')
        containers = box + mech + safe
        if (not any(p.stage == 'move' for p in points) and tuple(points) != containers) or (
            not points or (complete and not box)
        ):
            raise ValueError('路线须有武备箱段，且先到武备箱再到电子保险箱')
        if map_id == 'janus_high_b' and safe:
            raise ValueError('B 暂不支持电子保险箱段')
        if complete and map_id == 'janus_high_a' and len(safe) < 3:
            raise ValueError('路线必须先到武备箱，再到电子保险箱')
        if check_roles and box and [p.role for p in box] != ['turn'] * (len(box) - 1) + ['target']:
            raise ValueError('武备箱段必须以交互目标结束，前面只能放转折点')
        if check_roles and safe and [p.role for p in safe] != ['entry'] + ['turn'] * (len(safe) - 3) + ['approach', 'target']:
            raise ValueError('保险箱段顺序须为入口、转折、接近、交互目标')
        if any(math.dist(a.xy, b.xy) < 0.1 for a, b in zip(points, points[1:], strict=False)):
            raise ValueError('相邻路点不能重合')
        return route
