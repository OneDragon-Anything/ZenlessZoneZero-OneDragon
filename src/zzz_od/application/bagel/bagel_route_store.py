"""贝果路线与出生点的存储：加载、写入保护、开启选择与旧数据迁移。

文件布局（均在工作目录下）：

- ``assets/game_data/bagel/spawn_points.yml``：出生点清单，Git 跟踪。
- ``config/bagel/routes/<标识>.sample.route.json``：默认路线，Git 跟踪，内容只读。
- ``config/bagel/routes/custom_<标识>.route.json``：自定义路线，Git 忽略。
- ``config/bagel/route_settings.yml``：每个出生点当前开启的路线，Git 忽略。

开启选择每个出生点只存一个路线引用或 ``null``，天然保证同一出生点最多开启一条。
路线文件不保存开关状态。界面、录制器和执行器都通过本模块读写，不自行拼路径。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_route_model import (
    LEGACY_ROUTE_VERSION,
    SOURCE_CUSTOM,
    SOURCE_DEFAULT,
    BagelRoute,
    BagelRoutePoint,
    BagelRouteRef,
    BagelSpawnPoint,
    check_route_start,
    now_iso,
    validate_route_name,
)

SPAWN_FILE: tuple[str, ...] = ('assets', 'game_data', 'bagel', 'spawn_points.yml')
"""出生点清单相对工作目录的路径。"""

CONFIG_DIR: tuple[str, ...] = ('config', 'bagel')
"""路线配置目录相对工作目录的路径。"""

LEGACY_DIR_NAME: str = 'bagel_routes'
"""旧版路线目录，位于工作目录下；只在迁移时读取。"""

SAMPLE_SUFFIX: str = '.sample.route.json'
"""默认路线文件后缀。"""

ROUTE_SUFFIX: str = '.route.json'
"""路线文件后缀；自定义路线只用这个后缀。"""

CUSTOM_PREFIX: str = 'custom_'
"""自定义路线标识前缀。"""

CUSTOM_ID_PATTERN: re.Pattern[str] = re.compile(r'^custom_[0-9a-z_]{1,48}$')
"""自定义路线标识的合法形式；写入前检查，防止借标识写到默认路线或目录外。"""

SETTINGS_VERSION: int = 1
"""开启选择配置的格式版本。"""

class BagelRouteConfigError(Exception):
    """路线配置无法使用：配置损坏、引用失效或写入被拒绝。"""


@dataclass
class BagelRouteCatalog:
    """一次加载得到的全部出生点、路线与开启选择。"""

    spawns: list[BagelSpawnPoint]
    routes: list[BagelRoute]
    active: dict[str, BagelRouteRef | None]
    """出生点标识 → 当前开启的路线引用；缺少记录按关闭处理。"""
    errors: list[str] = field(default_factory=list)
    """加载时跳过的损坏文件等问题，供界面提示。"""

    def spawn(self, spawn_id: str) -> BagelSpawnPoint | None:
        """按标识找出生点。"""
        return next((item for item in self.spawns if item.spawn_id == spawn_id), None)

    def route(self, ref: BagelRouteRef) -> BagelRoute | None:
        """按引用找路线。"""
        return next((item for item in self.routes if item.ref == ref), None)

    def routes_for(self, spawn_id: str) -> list[BagelRoute]:
        """绑定到某个出生点的全部路线。"""
        return [item for item in self.routes if item.spawn_id == spawn_id]

    def active_ref(self, spawn_id: str) -> BagelRouteRef | None:
        """某个出生点当前开启的路线引用。"""
        return self.active.get(spawn_id)

    def is_active(self, route: BagelRoute) -> bool:
        """路线是否为所绑定出生点当前开启的路线。"""
        return self.active.get(route.spawn_id) == route.ref

    def selection_problem(self, spawn_id: str) -> str | None:
        """检查某个出生点的开启选择能否执行。

        Returns:
            选择无效时的原因；未开启或有效时返回 None。
        """
        ref = self.active.get(spawn_id)
        if ref is None:
            return None
        spawn = self.spawn(spawn_id)
        if spawn is None:
            return f'出生点 {spawn_id} 未登记'
        route = self.route(ref)
        if route is None:
            return f'{spawn.name}开启的路线 {ref} 不存在或已损坏'
        if route.spawn_id != spawn_id:
            return f'{spawn.name}开启的路线「{route.name}」绑定的是其他出生点'
        problem = check_route_start(route, spawn)
        if problem is not None:
            return f'{spawn.name}开启的路线「{route.name}」无法开始：{problem}'
        return None

    def selection_problems(self) -> list[str]:
        """全部出生点开启选择中的问题。"""
        problems = [self.selection_problem(spawn_id) for spawn_id in self.active]
        return [item for item in problems if item is not None]

    def active_count(self) -> int:
        """开启了路线的出生点个数。"""
        return sum(1 for ref in self.active.values() if ref is not None)


class BagelRouteStore:
    """路线文件与开启选择的读写入口。"""

    def __init__(self, work_dir: Path | None = None) -> None:
        """
        Args:
            work_dir: 工作目录；None 表示使用程序工作目录。离线核对时可传临时目录。
        """
        self.work_dir: Path = work_dir if work_dir is not None else Path(os_utils.get_work_dir())
        self.config_dir: Path = self.work_dir.joinpath(*CONFIG_DIR)
        self.routes_dir: Path = self.config_dir / 'routes'
        self.settings_path: Path = self.config_dir / 'route_settings.yml'
        self.legacy_dir: Path = self.work_dir / LEGACY_DIR_NAME
        self.spawn_path: Path = self.work_dir.joinpath(*SPAWN_FILE)

    # ---------- 读取 ----------

    def load_spawns(self) -> list[BagelSpawnPoint]:
        """读出出生点清单。

        Raises:
            BagelRouteConfigError: 清单缺失或格式错误。
        """
        try:
            data = yaml.safe_load(self.spawn_path.read_text(encoding='utf-8'))
            spawns = [
                BagelSpawnPoint(
                    spawn_id=str(item['id']),
                    name=str(item['name']),
                    layer=str(item['layer']),
                    x=float(item['x']),
                    y=float(item['y']),
                    radius=float(item['radius']),
                    initial_route=item.get('initial_route') or None,
                )
                for item in data['spawn_points']
            ]
        except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as error:
            raise BagelRouteConfigError(f'出生点清单无法读取：{error}') from error
        ids = [item.spawn_id for item in spawns]
        if len(set(ids)) != len(ids):
            raise BagelRouteConfigError('出生点清单中有重复标识')
        return spawns

    def load_routes(self) -> tuple[list[BagelRoute], list[str]]:
        """读出默认与自定义路线，损坏的文件跳过并记录原因。

        Returns:
            (路线列表, 问题列表)。默认路线在前，各自按名称排列。
        """
        routes: list[BagelRoute] = []
        errors: list[str] = []
        if not self.routes_dir.is_dir():
            return routes, errors
        for path in sorted(self.routes_dir.glob(f'*{ROUTE_SUFFIX}')):
            source = SOURCE_DEFAULT if path.name.endswith(SAMPLE_SUFFIX) else SOURCE_CUSTOM
            try:
                route = self._read_route(path, source)
            except (OSError, ValueError) as error:
                log.warning('跳过损坏的贝果路线文件 %s：%s', path.name, error)
                errors.append(f'{path.name}：{error}')
                continue
            routes.append(route)
        routes.sort(key=lambda item: (item.source != SOURCE_DEFAULT, item.name))
        return routes, errors

    def load_catalog(self) -> BagelRouteCatalog:
        """读出出生点、路线与开启选择；配置不存在时先迁移或初始化。

        Raises:
            BagelRouteConfigError: 出生点清单或开启选择配置损坏。
        """
        spawns = self.load_spawns()
        self._ensure_settings(spawns)
        routes, errors = self.load_routes()
        active = self._read_settings()
        # 已登记但没有记录的出生点按关闭处理；新发布的默认路线不抢占用户选择。
        for spawn in spawns:
            active.setdefault(spawn.spawn_id, None)
        catalog = BagelRouteCatalog(spawns, routes, active, errors)
        for spawn_id in list(active):
            if catalog.spawn(spawn_id) is None:
                errors.append(f'开启选择中的出生点 {spawn_id} 未登记，已忽略')
                del active[spawn_id]
        return catalog

    def load_route(self, ref: BagelRouteRef) -> BagelRoute:
        """按引用读出一条路线。

        Raises:
            BagelRouteConfigError: 路线不存在或损坏。
        """
        path = self._route_path(ref)
        if not path.is_file():
            raise BagelRouteConfigError(f'路线不存在：{ref}')
        try:
            return self._read_route(path, ref.source)
        except (OSError, ValueError) as error:
            raise BagelRouteConfigError(f'路线 {ref} 无法读取：{error}') from error

    def active_route(self, spawn_id: str) -> BagelRoute | None:
        """读出某个出生点当前开启的路线快照。

        Returns:
            开启的路线；该出生点没有开启路线时返回 None。

        Raises:
            BagelRouteConfigError: 配置损坏，或开启的路线无效。
        """
        catalog = self.load_catalog()
        problem = catalog.selection_problem(spawn_id)
        if problem is not None:
            raise BagelRouteConfigError(problem)
        ref = catalog.active_ref(spawn_id)
        if ref is None:
            return None
        route = catalog.route(ref)
        return route.copy() if route is not None else None

    # ---------- 写入 ----------

    def set_active_route(self, spawn_id: str, ref: BagelRouteRef | None) -> None:
        """设置某个出生点当前开启的路线；None 表示关闭该出生点的全部路线。

        Raises:
            BagelRouteConfigError: 出生点未登记、路线不存在或绑定的是其他出生点。
        """
        catalog = self.load_catalog()
        if catalog.spawn(spawn_id) is None:
            raise BagelRouteConfigError(f'出生点未登记：{spawn_id}')
        if ref is not None:
            route = catalog.route(ref)
            if route is None:
                raise BagelRouteConfigError(f'路线不存在：{ref}')
            if route.spawn_id != spawn_id:
                raise BagelRouteConfigError(f'路线「{route.name}」绑定的是其他出生点')
            problem = check_route_start(route, catalog.spawn(spawn_id))
            if problem is not None:
                raise BagelRouteConfigError(f'路线「{route.name}」无法开启：{problem}')
        catalog.active[spawn_id] = ref
        self._write_settings(catalog.active)

    def create_custom_route(
        self, name: str, spawn_id: str,
        points: list[BagelRoutePoint] | None = None, activate: bool = False,
        started_at: str | None = None,
    ) -> BagelRoute:
        """新建一条自定义路线。

        Args:
            name: 显示名称，不能与已有路线重名。
            spawn_id: 绑定的出生点。
            points: 点位；None 表示只放一个位于出生点坐标的途径点。
            activate: 创建后是否开启，开启会替换该出生点原来开启的路线。
            started_at: 路线开始时间；None 表示当前时间。

        Returns:
            已保存的路线。

        Raises:
            ValueError: 名称无效或重名。
            BagelRouteConfigError: 出生点未登记或写入失败。
        """
        catalog = self.load_catalog()
        spawn = catalog.spawn(spawn_id)
        if spawn is None:
            raise BagelRouteConfigError(f'出生点未登记：{spawn_id}')
        name = self._unique_name_check(catalog, name)
        if points is None:
            points = [BagelRoutePoint(round(spawn.x), round(spawn.y), spawn.layer, 'beacon')]
        route = BagelRoute(
            route_id=self._new_custom_id(),
            name=name,
            spawn_id=spawn_id,
            source=SOURCE_CUSTOM,
            started_at=started_at or now_iso(),
            ended_at=now_iso(),
            points=list(points),
        )
        self._write_route(route)
        if activate:
            self.set_active_route(spawn_id, route.ref)
        return route

    def copy_route(self, ref: BagelRouteRef, name: str) -> BagelRoute:
        """复制一条路线为新的自定义路线，副本初始关闭。

        Raises:
            ValueError: 名称无效或重名。
            BagelRouteConfigError: 源路线不存在或写入失败。
        """
        source = self.load_route(ref)
        return self.create_custom_route(name, source.spawn_id, points=list(source.points))

    def save_custom_route(self, route_id: str, points: list[BagelRoutePoint]) -> BagelRoute:
        """保存自定义路线的节点；默认路线拒绝写入。

        Raises:
            BagelRouteConfigError: 不是自定义路线、路线不存在或写入失败。
            ValueError: 节点无效。
        """
        ref = self._custom_ref(route_id)
        route = self.load_route(ref)
        spawn = next((item for item in self.load_spawns() if item.spawn_id == route.spawn_id), None)
        if spawn is None:
            raise BagelRouteConfigError(f'路线绑定的出生点未登记：{route.spawn_id}')
        route.points = list(points)
        problem = check_route_start(route, spawn)
        if problem is not None:
            raise ValueError(problem)
        route.ended_at = now_iso()
        self._write_route(route)
        return route

    def rename_custom_route(self, route_id: str, name: str) -> BagelRoute:
        """修改自定义路线的显示名称；标识与文件名不变。

        Raises:
            ValueError: 名称无效或重名。
            BagelRouteConfigError: 不是自定义路线或路线不存在。
        """
        ref = self._custom_ref(route_id)
        catalog = self.load_catalog()
        route = catalog.route(ref)
        if route is None:
            raise BagelRouteConfigError(f'路线不存在：{ref}')
        route.name = self._unique_name_check(catalog, name, ignore=ref)
        self._write_route(route)
        return route

    def delete_custom_route(self, route_id: str) -> None:
        """删除一条自定义路线。

        路线正在开启时先把对应出生点置为关闭，再删除文件；不自动开启其他路线。
        删除失败时开启选择保持关闭，避免留下指向已删除文件的引用。

        Raises:
            BagelRouteConfigError: 不是自定义路线、路线不存在或删除失败。
        """
        ref = self._custom_ref(route_id)
        path = self._route_path(ref)
        if not path.is_file():
            raise BagelRouteConfigError(f'路线不存在：{ref}')
        catalog = self.load_catalog()
        changed = False
        for spawn_id, active in catalog.active.items():
            if active == ref:
                catalog.active[spawn_id] = None
                changed = True
        if changed:
            self._write_settings(catalog.active)
        try:
            path.unlink()
        except OSError as error:
            raise BagelRouteConfigError(f'删除路线文件失败：{error}') from error

    def unique_name(self, base: str) -> str:
        """在 base 后追加序号，得到一个不重名的路线名称。"""
        names = {route.name for route in self.load_routes()[0]}
        if base not in names:
            return base
        index = 2
        while f'{base}{index}' in names:
            index += 1
        return f'{base}{index}'

    # ---------- 迁移与初始化 ----------

    def _ensure_settings(self, spawns: list[BagelSpawnPoint]) -> None:
        """开启选择配置不存在时，迁移旧数据或按出生点清单初始化。

        配置已存在时不做任何事：配置损坏由读取时报错，不当作首次安装重新启用默认路线。
        """
        if self.settings_path.exists():
            return
        legacy_files = sorted(self.legacy_dir.glob(f'*{ROUTE_SUFFIX}')) if self.legacy_dir.is_dir() else []
        if legacy_files:
            active = self._migrate_legacy(spawns, legacy_files)
        else:
            active = self._initial_selection(spawns)
        self._write_settings(active)

    def _initial_selection(self, spawns: list[BagelSpawnPoint]) -> dict[str, BagelRouteRef | None]:
        """首次安装的开启选择：只引用存在的默认路线。"""
        routes, _errors = self.load_routes()
        defaults = {route.route_id: route for route in routes if route.source == SOURCE_DEFAULT}
        active: dict[str, BagelRouteRef | None] = {}
        for spawn in spawns:
            route = defaults.get(spawn.initial_route) if spawn.initial_route else None
            if route is not None and route.spawn_id == spawn.spawn_id:
                active[spawn.spawn_id] = route.ref
            else:
                active[spawn.spawn_id] = None
        log.info('贝果路线：首次使用，按出生点清单初始化开启选择')
        return active

    def _migrate_legacy(
        self, spawns: list[BagelSpawnPoint], legacy_files: list[Path],
    ) -> dict[str, BagelRouteRef | None]:
        """把旧版 ``bagel_routes`` 迁移成新的路线与开启选择。

        - 与默认路线同标识且节点一致：沿用旧开关。
        - 与默认路线同标识但节点被修改：另存为自定义路线，旧开关作用到该副本。
        - 其他旧路线：首点只落在一个出生点识别半径内时，另存为绑定该点的自定义路线。
        - 绑定不了或损坏的文件只留在备份中，并写日志列出。
        - 同一出生点有多条旧路线启用时，全部按关闭处理，由用户在编辑器中选择。

        迁移前把旧目录整体复制到 ``config/bagel/legacy_routes_backup``，原目录保持不动。
        """
        backup = self.config_dir / 'legacy_routes_backup' / datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copytree(self.legacy_dir, backup, dirs_exist_ok=True)
        log.info('贝果路线：开始迁移旧版路线 %s 个，备份在 %s', len(legacy_files), backup)

        routes, _errors = self.load_routes()
        defaults = {route.route_id: route for route in routes if route.source == SOURCE_DEFAULT}
        spawn_by_id = {spawn.spawn_id: spawn for spawn in spawns}
        enabled_refs: dict[str, list[BagelRouteRef]] = {}
        pending: list[str] = []
        for path in legacy_files:
            try:
                route_id, enabled, started_at, points = _read_legacy_route(path)
            except (OSError, ValueError) as error:
                pending.append(f'{path.name}（无法读取：{error}）')
                continue
            default = defaults.get(route_id)
            if default is not None:
                spawn_id = default.spawn_id
                if [p.to_dict() for p in points] == [p.to_dict() for p in default.points]:
                    ref = default.ref
                else:
                    ref = self._save_migrated(f'{route_id}-旧版修改', spawn_id, points, started_at).ref
                    log.info('贝果路线：%s 节点与默认路线不同，已另存为自定义路线', route_id)
            else:
                candidates = [
                    spawn for spawn in spawns
                    if check_route_start(BagelRoute(route_id, route_id, spawn.spawn_id, points=points), spawn) is None
                ]
                if len(candidates) != 1:
                    reason = '首点不在任何出生点附近' if not candidates else '首点同时靠近多个出生点'
                    pending.append(f'{path.name}（{reason}）')
                    continue
                spawn_id = candidates[0].spawn_id
                ref = self._save_migrated(route_id, spawn_id, points, started_at).ref
            if enabled:
                enabled_refs.setdefault(spawn_id, []).append(ref)

        active: dict[str, BagelRouteRef | None] = {spawn.spawn_id: None for spawn in spawns}
        for spawn_id, refs in enabled_refs.items():
            if len(refs) == 1:
                active[spawn_id] = refs[0]
            else:
                log.warning(
                    '贝果路线：出生点 %s 有 %s 条旧路线同时启用，迁移后全部关闭，请在编辑器中选择',
                    spawn_by_id[spawn_id].name, len(refs),
                )
        if pending:
            log.warning('贝果路线：以下旧路线未迁移，原文件保留在备份中：%s', '；'.join(pending))
        log.info('贝果路线：旧版路线迁移完成')
        return active

    def _save_migrated(
        self, name: str, spawn_id: str, points: list[BagelRoutePoint], started_at: str,
    ) -> BagelRoute:
        """迁移时另存一条自定义路线；重名时追加序号，不触碰开启选择。"""
        catalog_names = {route.name for route in self.load_routes()[0]}
        unique = name
        index = 2
        while unique in catalog_names:
            unique = f'{name}{index}'
            index += 1
        route = BagelRoute(
            route_id=self._new_custom_id(),
            name=validate_route_name(unique[:40]),
            spawn_id=spawn_id,
            source=SOURCE_CUSTOM,
            started_at=started_at,
            ended_at=now_iso(),
            points=list(points),
        )
        self._write_route(route)
        return route

    # ---------- 内部 ----------

    def _route_path(self, ref: BagelRouteRef) -> Path:
        """引用对应的文件路径；标识不合法时拒绝。"""
        if ref.source == SOURCE_CUSTOM:
            if not CUSTOM_ID_PATTERN.match(ref.route_id):
                raise BagelRouteConfigError(f'自定义路线标识不合法：{ref.route_id}')
            return self.routes_dir / f'{ref.route_id}{ROUTE_SUFFIX}'
        if any(ch in ref.route_id for ch in '\\/:*?"<>|') or ref.route_id in ('.', '..'):
            raise BagelRouteConfigError(f'默认路线标识不合法：{ref.route_id}')
        return self.routes_dir / f'{ref.route_id}{SAMPLE_SUFFIX}'

    def _custom_ref(self, route_id: str) -> BagelRouteRef:
        """把标识当作自定义路线引用；默认路线或非法标识一律拒绝写入。"""
        if not CUSTOM_ID_PATTERN.match(route_id):
            raise BagelRouteConfigError('默认路线只读，复制后再修改')
        return BagelRouteRef(SOURCE_CUSTOM, route_id)

    def _read_route(self, path: Path, source: str) -> BagelRoute:
        """读出一个路线文件，并核对文件名与标识一致。"""
        route = BagelRoute.from_dict(json.loads(path.read_text(encoding='utf-8')), source)
        suffix = SAMPLE_SUFFIX if source == SOURCE_DEFAULT else ROUTE_SUFFIX
        if path.name != f'{route.route_id}{suffix}':
            raise ValueError(f'文件名与路线标识 {route.route_id} 不一致')
        if source == SOURCE_CUSTOM and not CUSTOM_ID_PATTERN.match(route.route_id):
            raise ValueError(f'自定义路线标识不合法：{route.route_id}')
        return route

    def _write_route(self, route: BagelRoute) -> None:
        """写入自定义路线：同目录临时文件写入、读回核对后替换。"""
        if route.source != SOURCE_CUSTOM:
            raise BagelRouteConfigError('默认路线只读，复制后再修改')
        path = self._route_path(route.ref)
        text = json.dumps(route.to_dict(), ensure_ascii=False, indent=1)

        def check(tmp: Path) -> None:
            reloaded = BagelRoute.from_dict(json.loads(tmp.read_text(encoding='utf-8')), SOURCE_CUSTOM)
            if len(reloaded.points) != len(route.points):
                raise ValueError(
                    f'读回点数不一致：写入 {len(route.points)}，读回 {len(reloaded.points)}',
                )

        _atomic_write(path, text, check)

    def _read_settings(self) -> dict[str, BagelRouteRef | None]:
        """读出开启选择；损坏时报错，不回退到默认值。"""
        try:
            data = yaml.safe_load(self.settings_path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('version') != SETTINGS_VERSION:
                raise ValueError('格式或版本不正确')
            raw = data.get('active_routes') or {}
            if not isinstance(raw, dict):
                raise ValueError('active_routes 不是映射')
            return {
                str(spawn_id): None if value is None else BagelRouteRef.from_json(value)
                for spawn_id, value in raw.items()
            }
        except (OSError, yaml.YAMLError, ValueError) as error:
            raise BagelRouteConfigError(
                f'路线开启配置 {self.settings_path.name} 已损坏：{error}',
            ) from error

    def _write_settings(self, active: dict[str, BagelRouteRef | None]) -> None:
        """一次写入整个开启选择。"""
        data = {
            'version': SETTINGS_VERSION,
            'active_routes': {
                spawn_id: None if ref is None else ref.to_json()
                for spawn_id, ref in active.items()
            },
        }
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)

        def check(tmp: Path) -> None:
            if yaml.safe_load(tmp.read_text(encoding='utf-8')) != data:
                raise ValueError('读回内容不一致')

        _atomic_write(self.settings_path, text, check)

    def _new_custom_id(self) -> str:
        """生成一个未被占用的自定义路线标识。"""
        while True:
            route_id = f'{CUSTOM_PREFIX}{datetime.now().strftime("%Y%m%d")}_{uuid.uuid4().hex[:8]}'
            if not (self.routes_dir / f'{route_id}{ROUTE_SUFFIX}').exists():
                return route_id

    @staticmethod
    def _unique_name_check(
        catalog: BagelRouteCatalog, name: str, ignore: BagelRouteRef | None = None,
    ) -> str:
        """校验名称合法且不与其他路线重名。"""
        name = validate_route_name(name)
        if any(route.name == name and route.ref != ignore for route in catalog.routes):
            raise ValueError(f'已经有同名路线：{name}')
        return name


def _atomic_write(path: Path, text: str, check: Any) -> None:
    """同目录临时文件写入，核对后原子替换；失败时保留原文件。

    Args:
        path: 目标文件。
        text: 文件内容。
        check: 接收临时文件路径的核对函数，不通过时抛异常。

    Raises:
        BagelRouteConfigError: 写入或核对失败。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp')
    try:
        tmp.write_text(text, encoding='utf-8')
        check(tmp)
        os.replace(tmp, path)
    except (OSError, ValueError, yaml.YAMLError) as error:
        tmp.unlink(missing_ok=True)
        raise BagelRouteConfigError(f'写入 {path.name} 失败：{error}') from error


def _read_legacy_route(path: Path) -> tuple[str, bool, str, list[BagelRoutePoint]]:
    """读出一份 v1 旧路线。

    Returns:
        (路线标识, 是否启用, 开始时间, 点位)。

    Raises:
        ValueError: 版本不对或数据不完整。
    """
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != LEGACY_ROUTE_VERSION:
        raise ValueError(f'不是旧版路线文件：版本 {data.get("version") if isinstance(data, dict) else "?"}')
    route_id = str(data.get('route_id', '')).strip()
    if not route_id:
        raise ValueError('缺少路线标识')
    points = [BagelRoutePoint.from_dict(item) for item in data.get('points') or []]
    if not points:
        raise ValueError('没有点')
    return route_id, bool(data.get('enabled', True)), str(data.get('started_at') or now_iso()), points
