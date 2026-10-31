"""贝果路线与出生点的数据定义及文件格式转换。

本模块只描述数据，不读写磁盘、不依赖 Qt 或录制器。读写与校验规则在
``bagel_route_store``，出生点匹配在 ``bagel_spawn``。

- 出生点：入场时角色所在的固定位置，独立于路线首点登记。
- 路线：一串有序点位，顺序本身就是路线；每条路线绑定一个出生点。
- 路线来源：默认路线随程序发布、内容只读；自定义路线由用户新增、录制或复制。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from math import hypot
from typing import Any

ROUTE_VERSION: int = 2
"""路线文件格式版本。v2 起路线必须绑定出生点，开关状态不再写进路线文件。"""

LEGACY_ROUTE_VERSION: int = 1
"""旧版路线文件格式版本，只在迁移旧数据时读取。"""

SOURCE_DEFAULT: str = 'default'
"""默认路线：随程序发布，内容只读。"""

SOURCE_CUSTOM: str = 'custom'
"""自定义路线：用户新增、录制或复制，可编辑。"""

SOURCES: tuple[str, ...] = (SOURCE_DEFAULT, SOURCE_CUSTOM)

BEACON: str = 'beacon'
"""途径点：纯路点，路过即可，不交互。"""

ELEVATOR: str = 'elevator'
"""电梯类型标识。进门后可能出楼层选项，也可能不出。"""

ELEVATOR_EXIT_FORWARD: str = 'forward'
ELEVATOR_EXIT_BACKWARD: str = 'backward'
"""电梯出来时朝哪个方向走。"""

POINT_KINDS: dict[str, tuple[str, str]] = {
    '1': (BEACON, '途径点'),
    '2': ('electronic_safe', '电子保险箱'),
    '3': ('mechanical_safe', '机械保险箱'),
    '4': ('box', '普通箱子'),
    '5': ('door', '门'),
    '6': (ELEVATOR, '电梯'),
}
"""打点键到（类型标识, 中文名）的映射。"""

KIND_ALIASES: dict[str, str] = {
    'briefcase': 'box',
}
"""旧路线文件里的类型名到当前类型名；改名后仍能读回。"""

KIND_LABELS: dict[str, str] = dict(POINT_KINDS.values())
"""类型标识到中文名，供界面与网页显示。"""

KIND_COLORS: dict[str, str] = {
    BEACON: '#2233b4',
    'electronic_safe': '#d97400',
    'mechanical_safe': '#8b3fc4',
    'box': '#1f8a4c',
    'door': '#238495',
    ELEVATOR: '#bc2f5e',
}
"""类型标识到标注色，与网页画点用的颜色是同一套。

电子=橙、机械=紫、普通箱=绿是语义色，其余三类按色相环拉开，
任意两类的色相至少差 41 度，肉眼可辨。
"""

POINT_MIN_DISTANCE: float = 8.0
"""同类型点与上一个点的最小间距；原地重复按不产生新点。"""

COORDINATE_LIMIT: float = 4000.0
"""点坐标的绝对值上限，防止网页或损坏文件传来离谱数值把路线写坏。"""

ROUTE_NAME_LIMIT: int = 40
"""路线显示名称的最大字符数。"""


def now_iso() -> str:
    """当前本地时间的 ISO 文本，精确到秒。"""
    return datetime.now().astimezone().isoformat(timespec='seconds')


def map_id_of(layer: str) -> str:
    """完整分层名中的地图标识，如 ``雅努斯幻境/Custom`` → ``雅努斯幻境``。"""
    return layer.split('/')[0]


@dataclass(frozen=True)
class BagelRoutePoint:
    """一个打点：全局坐标、所在分层与类型。

    点按打点顺序排列，顺序本身就是路线，不需要额外的连线数据。
    电梯点额外带两项进出电梯的参数。
    """

    x: float
    y: float
    layer: str
    kind: str
    elevator_option: str = ''
    """电梯要选的楼层文字，如「负二层站台」；空表示不选（直接进门）。"""
    elevator_exit: str = ELEVATOR_EXIT_FORWARD
    """出电梯往哪个方向走：forward 前进、backward 后退。"""

    def to_dict(self) -> dict[str, Any]:
        """生成可写入 JSON 的点。"""
        data: dict[str, Any] = {
            'x': round(self.x),
            'y': round(self.y),
            'layer': self.layer,
            'kind': self.kind,
        }
        if self.kind == ELEVATOR:
            data['elevator_option'] = self.elevator_option
            data['elevator_exit'] = self.elevator_exit
        return data

    @classmethod
    def from_dict(cls, item: Any) -> BagelRoutePoint:
        """校验并还原一个点；文件与网页传来的点都走这里。

        Args:
            item: 点位对象。

        Returns:
            校验后的点，坐标取整。

        Raises:
            ValueError: 字段缺失、类型不支持或坐标越界。
        """
        if not isinstance(item, dict):
            raise ValueError('点位不是对象')
        try:
            kind = KIND_ALIASES.get(str(item['kind']), str(item['kind']))
            layer = str(item['layer'])
            x = float(item['x'])
            y = float(item['y'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f'点位字段缺失或不是数字：{error}') from error
        if kind not in KIND_LABELS:
            raise ValueError(f'不支持的点的类型：{kind}')
        if not layer or '/' not in layer:
            raise ValueError(f'点位分层不完整：{layer}')
        if not (-COORDINATE_LIMIT <= x <= COORDINATE_LIMIT):
            raise ValueError(f'x 越界：{x}')
        if not (-COORDINATE_LIMIT <= y <= COORDINATE_LIMIT):
            raise ValueError(f'y 越界：{y}')
        option = str(item.get('elevator_option', '')).strip()
        exit_direction = str(item.get('elevator_exit', ELEVATOR_EXIT_FORWARD))
        if exit_direction not in (ELEVATOR_EXIT_FORWARD, ELEVATOR_EXIT_BACKWARD):
            raise ValueError(f'电梯出梯方向不支持：{exit_direction}')
        if kind != ELEVATOR:
            option = ''
            exit_direction = ELEVATOR_EXIT_FORWARD
        return cls(
            float(round(x)), float(round(y)), layer, kind,
            elevator_option=option, elevator_exit=exit_direction,
        )


@dataclass(frozen=True)
class BagelSpawnPoint:
    """一个已登记的出生点。

    出生点独立于路线首点：移动路线首点不改变出生点位置。
    """

    spawn_id: str
    """稳定标识，路线和开启选择都用它引用出生点。"""
    name: str
    """显示名称。"""
    layer: str
    """完整分层名，如 ``雅努斯幻境/Custom``。"""
    x: float
    y: float
    """全局坐标。"""
    radius: float
    """识别半径（地图像素）：定位结果与出生点坐标的距离不超过它才算命中。"""
    initial_route: str | None = None
    """首次安装时默认开启的默认路线标识；None 表示首次安装时不开启任何路线。"""

    @property
    def map_id(self) -> str:
        """出生点所在地图。"""
        return map_id_of(self.layer)

    def distance_to(self, x: float, y: float) -> float:
        """与某个全局坐标的距离。"""
        return hypot(self.x - x, self.y - y)

    def to_json(self) -> dict[str, Any]:
        """网页使用的出生点数据。"""
        return {
            'spawn_id': self.spawn_id,
            'name': self.name,
            'layer': self.layer,
            'map_id': self.map_id,
            'x': round(self.x),
            'y': round(self.y),
            'radius': self.radius,
        }


@dataclass(frozen=True)
class BagelRouteRef:
    """对一条路线的引用：来源加路线标识。

    默认与自定义路线分开存放，同一个标识只在各自来源内唯一，所以引用必须带来源。
    """

    source: str
    route_id: str

    def to_json(self) -> dict[str, str]:
        """写入配置或推给网页的形式。"""
        return {'source': self.source, 'route_id': self.route_id}

    @classmethod
    def from_json(cls, data: Any) -> BagelRouteRef:
        """从配置或网页还原引用。

        Raises:
            ValueError: 来源不支持或标识为空。
        """
        if not isinstance(data, dict):
            raise ValueError('路线引用不是对象')
        source = str(data.get('source', ''))
        route_id = str(data.get('route_id', '')).strip()
        if source not in SOURCES:
            raise ValueError(f'不支持的路线来源：{source}')
        if not route_id:
            raise ValueError('路线引用缺少标识')
        return cls(source, route_id)

    def __str__(self) -> str:
        return f'{self.source}:{self.route_id}'


@dataclass
class BagelRoute:
    """一条打点路线：有序点位，顺序即路径。"""

    route_id: str
    """路线标识，创建后不变，与文件名主干一致。"""
    name: str
    """显示名称；自定义路线可以改名，改名不改标识。"""
    spawn_id: str
    """绑定的出生点标识。"""
    source: str = SOURCE_CUSTOM
    """来源，由实际文件所在位置决定，不写进文件。"""
    started_at: str = field(default_factory=now_iso)
    ended_at: str | None = None
    points: list[BagelRoutePoint] = field(default_factory=list)

    @property
    def ref(self) -> BagelRouteRef:
        """指向本路线的引用。"""
        return BagelRouteRef(self.source, self.route_id)

    @property
    def readonly(self) -> bool:
        """默认路线内容只读。"""
        return self.source == SOURCE_DEFAULT

    @property
    def map_id(self) -> str:
        """路线首点所在地图；没有点时为空串。"""
        return map_id_of(self.points[0].layer) if self.points else ''

    def append_point(self, point: BagelRoutePoint) -> bool:
        """追加一个点；同类型且与上一个点太近时忽略。

        Args:
            point: 待追加的点。

        Returns:
            真正加入时返回 True。
        """
        if self.points:
            last = self.points[-1]
            if (
                last.kind == point.kind
                and last.layer == point.layer
                and hypot(last.x - point.x, last.y - point.y) < POINT_MIN_DISTANCE
            ):
                return False
        self.points.append(point)
        return True

    def pop_point(self) -> BagelRoutePoint | None:
        """删掉最后一个点，没有点时返回 None。"""
        if not self.points:
            return None
        return self.points.pop()

    def copy(self) -> BagelRoute:
        """生成独立副本，点位列表不与原路线共享。"""
        return replace(self, points=list(self.points))

    def to_dict(self) -> dict[str, Any]:
        """生成待写入文件的数据；来源由文件位置决定，不写入。"""
        return {
            'version': ROUTE_VERSION,
            'route_id': self.route_id,
            'name': self.name,
            'spawn_id': self.spawn_id,
            'started_at': self.started_at,
            'ended_at': self.ended_at,
            'points': [point.to_dict() for point in self.points],
        }

    def to_json(self, active: bool) -> dict[str, Any]:
        """网页使用的路线数据。

        Args:
            active: 是否为所绑定出生点当前开启的路线。
        """
        return {
            'source': self.source,
            'route_id': self.route_id,
            'name': self.name,
            'spawn_id': self.spawn_id,
            'active': active,
            'points': [point.to_dict() for point in self.points],
        }

    @classmethod
    def from_dict(cls, data: Any, source: str) -> BagelRoute:
        """从 v2 文件数据还原路线。

        Args:
            data: 文件内容。
            source: 文件所在位置决定的来源。

        Raises:
            ValueError: 版本不支持或数据不完整。
        """
        if not isinstance(data, dict):
            raise ValueError('路线文件不是对象')
        if data.get('version') != ROUTE_VERSION:
            raise ValueError(f'不支持的路线文件版本：{data.get("version")}')
        route_id = str(data.get('route_id', '')).strip()
        name = str(data.get('name', '')).strip()
        spawn_id = str(data.get('spawn_id', '')).strip()
        if not route_id or not name or not spawn_id:
            raise ValueError('路线缺少标识、名称或出生点')
        raw_points = data.get('points')
        if not isinstance(raw_points, list):
            raise ValueError('路线点位不是数组')
        return cls(
            route_id=route_id,
            name=name,
            spawn_id=spawn_id,
            source=source,
            started_at=str(data.get('started_at') or now_iso()),
            ended_at=data.get('ended_at'),
            points=[BagelRoutePoint.from_dict(item) for item in raw_points],
        )


def validate_route_name(name: str) -> str:
    """校验路线显示名称并去掉首尾空白。

    Raises:
        ValueError: 名称为空或过长。
    """
    name = name.strip()
    if not name:
        raise ValueError('路线名称不能为空')
    if len(name) > ROUTE_NAME_LIMIT:
        raise ValueError(f'路线名称不能超过 {ROUTE_NAME_LIMIT} 个字符')
    return name


def check_route_start(route: BagelRoute, spawn: BagelSpawnPoint) -> str | None:
    """检查路线首点能否从出生点开始执行。

    首点必须是途径点，与出生点在同一完整分层，且位于出生点识别半径内。

    Args:
        route: 待检查的路线。
        spawn: 路线绑定的出生点。

    Returns:
        不满足时返回原因；满足时返回 None。
    """
    if not route.points:
        return '路线没有点'
    first = route.points[0]
    if first.kind != BEACON:
        return f'首点必须是途径点，当前是{KIND_LABELS.get(first.kind, first.kind)}'
    if first.layer != spawn.layer:
        return f'首点分层 {first.layer} 与出生点分层 {spawn.layer} 不一致'
    distance = spawn.distance_to(first.x, first.y)
    if distance > spawn.radius:
        return f'首点距出生点 {distance:.0f}px，超出识别半径 {spawn.radius:.0f}px'
    return None
