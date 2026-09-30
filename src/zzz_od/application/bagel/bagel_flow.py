"""贝果局内流程、导航参数和开发草稿；正式运行只读取发布资源。"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import yaml

from one_dragon.utils import os_utils
from zzz_od.application.bagel.bagel_const import (
    NAV_CRUISE_DISTANCE,
    NAV_SAFE_BRAKE_DISTANCE,
)
from zzz_od.application.bagel.bagel_route import (
    MAP_LABELS,
    BagelRoute,
    BagelWaypoint,
    _number,
    resource_root,
)

ACTION_LABELS: dict[str, str] = {
    'spawn': '检查出生位置',
    'move': '移动到路点',
    'approach': '靠近交互目标',
    'interact': '按交互键',
    'unlock': '完成光圈解锁',
    'store': '装入安全箱',
    'close': '关闭搜查面板',
    'exit': '退出本局',
}
ACTION_CATEGORIES: dict[str, str] = {
    'spawn': '检查',
    'move': '移动',
    'approach': '移动',
    'interact': '交互',
    'unlock': '解锁',
    'store': '收集',
    'close': '界面',
    'exit': '退出',
}
ACTION_RULES: dict[str, str] = {
    'spawn': '只检查是否站在所选出生点，不移动角色。',
    'move': '只走到这一个路点并停下，不等待交互提示，也不按交互键。',
    'approach': '只靠近目标，看到对应交互提示后停下，不按交互键。',
    'interact': '请先站到出现交互提示和 F 图标的位置。只打开武备箱面板或电子保险箱解锁界面，不执行解锁或收集。',
    'unlock': '请先打开电子保险箱的光圈界面。只完成光圈解锁，等搜查面板出现后停止。',
    'store': '请先打开对应容器的搜查面板。等待搜索并把合适的物品装入安全箱，完成后保留面板。',
    'close': '只关闭搜查面板并回到局内。搜索尚未完成时会等待，不收集物品。',
    'exit': '请先关闭菜单，回到游戏画面。退出当前关卡并回到仓库界面，不存放或出售物品。',
}


def _text(value: object, label: str) -> str:
    """校验稳定标识及显示文本。"""
    if not isinstance(value, str) or not value.strip() or len(value) > 80:
        raise ValueError(f'{label}须为 1 至 80 个字符')
    return value.strip()


@dataclass(frozen=True)
class NavigationOptions:
    """仅记录覆盖项，默认值与导航执行共用。"""

    timeout: float | None = None
    brake_distance: float | None = None
    final_mode: str | None = None
    interaction_distance: float | None = None

    @property
    def effective_interaction_distance(self) -> float:
        """只在目标附近采信提示，避免第二个同类容器误认上一个。"""
        return (
            self.interaction_distance
            if self.interaction_distance is not None
            else NAV_CRUISE_DISTANCE
        )

    def effective_timeout(self, target: str) -> float:
        """返回整个移动步骤的时限。"""
        return (
            self.timeout
            if self.timeout is not None
            else (75 if target == 'safe' else 45)
        )

    @property
    def effective_brake_distance(self) -> float:
        """接近点提前松键距离。"""
        return (
            self.brake_distance
            if self.brake_distance is not None
            else NAV_SAFE_BRAKE_DISTANCE
        )

    def effective_final_mode(self, target: str) -> str:
        """保险箱沿最后一段方向碎步，武备箱默认靠坐标接近。"""
        return self.final_mode or ('short_steps' if target == 'safe' else 'coordinate')

    def to_dict(self) -> dict[str, Any]:
        """默认项不复制到文件中。"""
        return {
            key: value
            for key, value in (
                ('timeout', self.timeout),
                ('brake_distance', self.brake_distance),
                ('final_mode', self.final_mode),
                ('interaction_distance', self.interaction_distance),
            )
            if value is not None
        }

    @classmethod
    def from_dict(cls, data: object) -> NavigationOptions:
        """拒绝拼错字段、非有限参数和未定义模式。"""
        if not isinstance(data, dict) or set(data) - {
            'timeout',
            'brake_distance',
            'final_mode',
            'interaction_distance',
        }:
            raise ValueError('导航参数包含未知字段')
        timeout = (
            _number(data['timeout'], '导航超时', 1, 600) if 'timeout' in data else None
        )
        brake = (
            _number(data['brake_distance'], '停步距离', 0.1, 30)
            if 'brake_distance' in data
            else None
        )
        mode = data.get('final_mode')
        if mode is not None and mode not in ('short_steps', 'coordinate'):
            raise ValueError('未知末段移动方式')
        interaction = (
            _number(data['interaction_distance'], '交互采信距离', 0.1, 30)
            if 'interaction_distance' in data
            else None
        )
        return cls(timeout, brake, mode, interaction)


@dataclass(frozen=True)
class BagelStep:
    """每个移动步骤独立持有路点，名称不参与动作派发。"""

    id: str
    action: str
    name: str
    target: str | None = None
    waypoints: tuple[BagelWaypoint, ...] = ()
    navigation: NavigationOptions = NavigationOptions()

    def to_dict(self) -> dict[str, Any]:
        """序列化业务步骤。"""
        data: dict[str, Any] = {'id': self.id, 'action': self.action, 'name': self.name}
        if self.target is not None:
            data['target'] = self.target
        if self.action in ('move', 'approach'):
            data['waypoints'] = [point.to_dict() for point in self.waypoints]
            data['navigation'] = self.navigation.to_dict()
        return data

    def route(self, map_id: str) -> BagelRoute:
        """交给既有导航器的单段路线。"""
        return BagelRoute.from_dict(
            map_id,
            {'map_id': map_id, 'waypoints': [p.to_dict() for p in self.waypoints]},
            complete=False,
            check_roles=False,
        )


@dataclass(frozen=True)
class BagelFlow:
    """执行时不可变的局内流程快照。"""

    id: str
    name: str
    map_id: str
    steps: tuple[BagelStep, ...]

    def to_dict(self) -> dict[str, Any]:
        """草稿与正式资源共用结构。"""
        return {
            'version': 2,
            'id': self.id,
            'name': self.name,
            'map_id': self.map_id,
            'steps': [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: object, *, validate_order: bool = True) -> BagelFlow:
        """读取独立动作；旧版只在内存迁移，不改写源文件。"""
        if not isinstance(data, dict) or type(data.get('version')) is not int:
            raise ValueError('流程格式或版本无效')
        if data['version'] == 1:
            return split_legacy_flow(
                cls._from_legacy(data, validate_order=validate_order),
                validate_order=validate_order,
            )
        if data['version'] != 2:
            raise ValueError('流程格式或版本无效')
        if set(data) - {'version', 'id', 'name', 'map_id', 'steps'}:
            raise ValueError('流程包含未知字段')
        map_id = data.get('map_id')
        if not isinstance(map_id, str) or map_id not in MAP_LABELS:
            raise ValueError('流程包含未知地图')
        values = data.get('steps')
        if not isinstance(values, list) or len(values) > 300:
            raise ValueError('流程须为至多 300 个步骤的列表')
        steps: list[BagelStep] = []
        for value in values:
            if not isinstance(value, dict) or set(value) - {
                'id',
                'name',
                'action',
                'target',
                'waypoints',
                'navigation',
            }:
                raise ValueError('步骤格式或字段无效')
            action = value.get('action')
            if not isinstance(action, str) or action not in ACTION_LABELS:
                raise ValueError(f'未知业务动作：{action}')
            target = value.get('target')
            if action not in ('spawn', 'exit'):
                if target not in ('box', 'safe'):
                    raise ValueError('该动作须指定容器类型')
            elif target is not None:
                raise ValueError('该动作不接受目标参数')
            if action == 'unlock' and target != 'safe':
                raise ValueError('只有电子保险箱需要光圈解锁')
            if map_id == 'janus_high_b' and target == 'safe':
                raise ValueError('白鸽地图尚无电子保险箱资源')
            points: tuple[BagelWaypoint, ...] = ()
            navigation = NavigationOptions()
            if action in ('move', 'approach'):
                points = BagelRoute.from_dict(
                    map_id,
                    {'map_id': map_id, 'waypoints': value.get('waypoints')},
                    complete=False,
                    check_roles=False,
                ).waypoints
                navigation = NavigationOptions.from_dict(value.get('navigation', {}))
                if any(point.stage != target for point in points):
                    raise ValueError('移动步骤的路点与目标不一致')
                if action == 'move' and len(points) != 1:
                    raise ValueError('移动到路点每步只能包含一个路点')
                if action == 'approach':
                    short = navigation.effective_final_mode(target) == 'short_steps'
                    if len(points) != (2 if short else 1):
                        raise ValueError(
                            '小步靠近需要方向起点和目标两个路点；坐标靠近只需目标路点'
                        )
                    if points[-1].role != 'target':
                        raise ValueError('靠近步骤必须以交互目标结束')
                if any(not point.stop for point in points):
                    raise ValueError('独立移动步骤完成后必须停步')
            elif 'waypoints' in value or 'navigation' in value:
                raise ValueError('只有移动动作可以包含路点和导航参数')
            steps.append(
                BagelStep(
                    _text(value.get('id'), '步骤标识'),
                    action,
                    _text(value.get('name'), '步骤名称'),
                    target,
                    points,
                    navigation,
                )
            )
        if len({step.id for step in steps}) != len(steps):
            raise ValueError('步骤标识不能重复')
        flow = cls(
            _text(data.get('id'), '流程标识'),
            _text(data.get('name'), '流程名称'),
            map_id,
            tuple(steps),
        )
        if validate_order:
            flow.validate_order()
        return flow

    def validate_order(self) -> None:
        """完整流程显式表达靠近、交互、解锁、收集与关闭的先后关系。"""
        if (
            not self.steps
            or self.steps[0].action != 'spawn'
            or self.steps[-1].action != 'exit'
        ):
            raise ValueError('完整流程须从出生检查开始，以主动退出结束')
        arrived: str | None = None
        opened: str | None = None
        state = 'hud'
        collected = False
        for index, step in enumerate(self.steps):
            action = step.action
            if action == 'spawn':
                if index != 0:
                    raise ValueError('出生检查只能放在首步')
            elif action in ('move', 'approach', 'exit'):
                if state != 'hud':
                    raise ValueError('移动或退出前须收集并关闭搜查面板')
                if action == 'exit' and index != len(self.steps) - 1:
                    raise ValueError('主动退出后不能继续执行局内动作')
                arrived = step.target if action == 'approach' else None
            elif action == 'interact':
                if state != 'hud' or arrived != step.target:
                    raise ValueError(f'{step.name}前须靠近对应的交互目标')
                opened = step.target
                state = 'unlock' if opened == 'safe' else 'search'
                collected = False
            elif action == 'unlock':
                if state != 'unlock' or opened != 'safe':
                    raise ValueError('光圈解锁前须与电子保险箱交互')
                state = 'search'
            elif action == 'store':
                if state != 'search' or opened != step.target or collected:
                    raise ValueError(f'{step.name}前须打开对应容器，且不能重复收集')
                collected = True
            elif action == 'close':
                if state != 'search' or opened != step.target or not collected:
                    raise ValueError('关闭搜查面板前须完成对应容器的收集')
                state = 'hud'
                opened = arrived = None

    @classmethod
    def _from_legacy(cls, data: object, *, validate_order: bool = True) -> BagelFlow:
        """严格校验旧版，再交给迁移函数拆分动作。"""
        if (
            not isinstance(data, dict)
            or type(data.get('version')) is not int
            or data['version'] != 1
        ):
            raise ValueError('流程格式或版本无效')
        if set(data) - {'version', 'id', 'name', 'map_id', 'steps'}:
            raise ValueError('流程包含未知字段')
        map_id = data.get('map_id')
        if not isinstance(map_id, str) or map_id not in MAP_LABELS:
            raise ValueError('流程包含未知地图')
        values = data.get('steps')
        if not isinstance(values, list) or len(values) > 100:
            raise ValueError('流程须为至多 100 个步骤的列表')
        steps: list[BagelStep] = []
        for value in values:
            if not isinstance(value, dict) or set(value) - {
                'id',
                'name',
                'action',
                'target',
                'waypoints',
                'navigation',
            }:
                raise ValueError('步骤格式或字段无效')
            action = value.get('action')
            if not isinstance(action, str) or action not in (
                'spawn',
                'move',
                'open_box',
                'unlock_safe',
                'store',
                'exit',
            ):
                raise ValueError(f'未知业务动作：{action}')
            target = value.get('target')
            if action in ('move', 'store'):
                if target not in ('box', 'safe'):
                    raise ValueError('移动或收集须指定容器类型')
            elif target is not None:
                raise ValueError('该动作不接受目标参数')
            if map_id == 'janus_high_b' and (
                target == 'safe' or action == 'unlock_safe'
            ):
                raise ValueError('白鸽地图尚无电子保险箱资源')
            points: tuple[BagelWaypoint, ...] = ()
            navigation = NavigationOptions()
            if action == 'move':
                route = BagelRoute.from_dict(
                    map_id,
                    {'map_id': map_id, 'waypoints': value.get('waypoints')},
                    complete=False,
                )
                if any(point.stage != target for point in route.waypoints):
                    raise ValueError('移动步骤的路点与目标不一致')
                points = route.waypoints
                navigation = NavigationOptions.from_dict(value.get('navigation', {}))
                if navigation.effective_final_mode(target) == 'short_steps':
                    if len(points) < 2:
                        raise ValueError('沿末段碎步至少需要两个不同路点定义方向')
                    if not points[-2].stop:
                        raise ValueError('沿末段碎步前的接近点必须停步')
                if not points[-1].stop:
                    raise ValueError('交互目标必须停步')
            elif 'waypoints' in value or 'navigation' in value:
                raise ValueError('只有移动动作可以包含路点和导航参数')
            steps.append(
                BagelStep(
                    _text(value.get('id'), '步骤标识'),
                    action,
                    _text(value.get('name'), '步骤名称'),
                    target,
                    points,
                    navigation,
                )
            )
        if len({step.id for step in steps}) != len(steps):
            raise ValueError('步骤标识不能重复')
        flow = cls(
            _text(data.get('id'), '流程标识'),
            _text(data.get('name'), '流程名称'),
            map_id,
            tuple(steps),
        )
        if validate_order:
            flow._validate_legacy_order()
        return flow

    def _validate_legacy_order(self) -> None:
        """检查顺序前置条件；真实画面仍须运行时验证。"""
        if (
            not self.steps
            or self.steps[0].action != 'spawn'
            or self.steps[-1].action != 'exit'
        ):
            raise ValueError('完整流程须从出生检查开始，以主动退出结束')
        arrived: str | None = None
        opened: str | None = None
        for index, step in enumerate(self.steps):
            if step.action == 'spawn' and index != 0:
                raise ValueError('出生检查只能放在首步')
            if step.action == 'exit' and index != len(self.steps) - 1:
                raise ValueError('主动退出后不能继续执行局内动作')
            if opened is not None and step.action != 'store':
                raise ValueError('打开容器后须收集并关闭搜查面板')
            if step.action == 'move':
                arrived = step.target
            elif step.action in ('open_box', 'unlock_safe'):
                target = 'box' if step.action == 'open_box' else 'safe'
                if arrived != target:
                    raise ValueError(f'{step.name}前须有对应的移动步骤')
                opened = target
            elif step.action == 'store':
                if opened != step.target:
                    raise ValueError(f'{step.name}前须打开对应容器')
                opened = arrived = None


def split_legacy_flow(flow: BagelFlow, *, validate_order: bool = True) -> BagelFlow:
    """将旧复合步骤拆成独立动作，坐标与参数保留，新增标识稳定生成。"""
    steps: list[BagelStep] = []
    for step in flow.steps:

        def derived_id(part: str, source: BagelStep = step) -> str:
            """根据旧标识和动作位置生成重复读取不变的标识。"""
            return f'{source.id[:40]}_{uuid5(NAMESPACE_URL, f"bagel:{flow.id}:{source.id}:{part}").hex}'

        if step.action == 'move':
            for index, point in enumerate(step.waypoints[:-1]):
                steps.append(
                    BagelStep(
                        step.id if index == 0 else derived_id(f'point-{index}'),
                        'move',
                        f'走到{point.name}',
                        step.target,
                        (replace(point, stop=True),),
                        step.navigation,
                    )
                )
            short = step.navigation.effective_final_mode(step.target) == 'short_steps'
            points = step.waypoints[-2:] if short else step.waypoints[-1:]
            steps.append(
                BagelStep(
                    step.id if len(step.waypoints) == 1 else derived_id('approach'),
                    'approach',
                    f'靠近{step.waypoints[-1].name}',
                    step.target,
                    tuple(replace(point, stop=True) for point in points),
                    step.navigation,
                )
            )
        elif step.action in ('open_box', 'unlock_safe'):
            target = 'box' if step.action == 'open_box' else 'safe'
            steps.append(
                BagelStep(
                    step.id if target == 'box' else derived_id('interact'),
                    'interact',
                    '打开武备箱' if target == 'box' else '打开电子保险箱解锁界面',
                    target,
                )
            )
            if target == 'safe':
                steps.append(
                    BagelStep(step.id, 'unlock', '完成电子保险箱光圈解锁', 'safe')
                )
        elif step.action == 'store':
            steps.append(step)
            steps.append(
                BagelStep(derived_id('close'), 'close', '关闭搜查面板', step.target)
            )
        else:
            steps.append(step)
    return BagelFlow.from_dict(
        replace(flow, steps=tuple(steps)).to_dict(), validate_order=validate_order
    )


def flow_from_route(route: BagelRoute) -> BagelFlow:
    """显式导入旧路点，补齐原业务动作，保持旧文件不变。"""
    steps = [BagelStep('spawn', 'spawn', '检查出生位置')]
    for target, title, action in (
        ('box', '武备箱', 'open_box'),
        ('safe', '电子保险箱', 'unlock_safe'),
    ):
        points = route.points_for(target)
        if not points:
            continue
        steps.extend(
            (
                BagelStep(f'move_{target}', 'move', f'移动到{title}', target, points),
                BagelStep(f'open_{target}', action, f'打开{title}'),
                BagelStep(f'store_{target}', 'store', f'{title}装入安全箱', target),
            )
        )
    steps.append(BagelStep('exit', 'exit', '主动退出'))
    return BagelFlow.from_dict(
        dict(
            BagelFlow(
                route.map_id, MAP_LABELS[route.map_id], route.map_id, tuple(steps)
            ).to_dict(),
            version=1,
        )
    )


def read_flow(path: Path) -> BagelFlow:
    """损坏文件直接报错，不能静默回退。"""
    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
    except yaml.YAMLError as error:
        raise ValueError(f'流程 YAML 无效：{path}') from error
    return BagelFlow.from_dict(data)


def load_published_flow(map_id: str) -> BagelFlow:
    """普通任务只读取仓库内正式资源。"""
    flow = read_flow(resource_root(map_id) / 'flow.yml')
    if flow.map_id != map_id:
        raise ValueError('流程与资源目录的地图标识不一致')
    return flow


def draft_path(map_id: str) -> Path:
    """开发草稿与账号覆盖配置分开存储。"""
    if map_id not in MAP_LABELS:
        raise ValueError('未知地图')
    return (
        Path(os_utils.get_work_dir())
        / 'config'
        / 'devtools'
        / 'bagel'
        / f'{map_id}.yml'
    )


def write_flow(path: Path, flow: BagelFlow) -> None:
    """完整校验后同目录原子替换并回读。"""
    checked = BagelFlow.from_dict(flow.to_dict())
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f'.{path.stem}-', suffix='.tmp', dir=path.parent
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            yaml.safe_dump(
                checked.to_dict(), stream, allow_unicode=True, sort_keys=False
            )
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    if read_flow(path) != checked:
        raise OSError('流程写入后回读不一致')
