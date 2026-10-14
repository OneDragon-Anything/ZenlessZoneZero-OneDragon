"""Independent ordered stock-deficit task, using isolated native one-run plans."""

import inspect
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from zzz_od.application.inventory_support.runtime import (
    import_support,
    inventory_root,
    valid_game_path,
)

ROOT = inventory_root()
APP_ID = 'inventory_maintain'
ROUTES = {
    'basic-physical-chip': {
        'name': '刚性测试',
        'type': '代理人技能',
        'mission': '刚性测试',
        'cost': 20,
        'materials': ['basic-physical-chip'],
    },
    'basic-attack-seal': {
        'name': '强攻演练',
        'type': '代理人晋升',
        'mission': '强攻演练',
        'cost': 20,
        'materials': ['basic-attack-seal'],
    },
    'support-component': {
        'name': '支援分频试验',
        'type': '音擎改装',
        'mission': '支援分频试验',
        'cost': 20,
        'materials': ['support-component'],
    },
    'w-engine-energy-module': {
        'name': '音擎专项',
        'type': '基础材料',
        'mission': '音擎专项',
        'cost': 20,
        'materials': ['w-engine-energy-module'],
    },
    'senior-investigator-log': {
        'name': '调查专项',
        'type': '基础材料',
        'mission': '调查专项',
        'cost': 20,
        'materials': ['senior-investigator-log'],
    },
    'denny': {
        'name': '赏金专项',
        'type': '基础材料',
        'mission': '赏金专项',
        'cost': 20,
        'materials': ['denny'],
    },
    'ferocious-grip': {
        'name': '恶名狩猎 · 初生死路屠夫',
        'category': '恶名狩猎',
        'type': '初生死路屠夫',
        'mission': None,
        'cost': 60,
        'materials': ['ferocious-grip'],
    },
    'advanced-attack-seal': {
        'name': '强攻演练',
        'type': '代理人晋升',
        'mission': '强攻演练',
        'cost': 20,
        'materials': ['advanced-attack-seal'],
    },
    'pioneer-certification-seal': {
        'name': '强攻演练',
        'type': '代理人晋升',
        'mission': '强攻演练',
        'cost': 20,
        'materials': ['pioneer-certification-seal'],
    },
    'advanced-physical-chip': {
        'name': '刚性测试',
        'type': '代理人技能',
        'mission': '刚性测试',
        'cost': 20,
        'materials': ['advanced-physical-chip'],
    },
    'specialized-physical-chip': {
        'name': '刚性测试',
        'type': '代理人技能',
        'mission': '刚性测试',
        'cost': 20,
        'materials': ['specialized-physical-chip'],
    },
    'basic-freeze-chip': {
        'name': '冰结测试',
        'type': '代理人技能',
        'mission': '冰结测试',
        'cost': 20,
        'materials': ['basic-freeze-chip'],
    },
    'advanced-freeze-chip': {
        'name': '冰结测试',
        'type': '代理人技能',
        'mission': '冰结测试',
        'cost': 20,
        'materials': ['advanced-freeze-chip'],
    },
    'specialized-freeze-chip': {
        'name': '冰结测试',
        'type': '代理人技能',
        'mission': '冰结测试',
        'cost': 20,
        'materials': ['specialized-freeze-chip'],
    },
    'higher-dimensional-data-caustic-thorn': {
        'name': '专业挑战室 · 秽息行者·蝎骸',
        'category': '专业挑战室',
        'type': '秽息行者·蝎骸',
        'mission': None,
        'cost': 40,
        'materials': ['higher-dimensional-data-caustic-thorn'],
    },
    'higher-dimensional-data-dream-corroded-iron': {
        'name': '专业挑战室 · 秽蚀·狛野真斗',
        'category': '专业挑战室',
        'type': '秽蚀·狛野真斗',
        'mission': None,
        'cost': 40,
        'materials': ['higher-dimensional-data-dream-corroded-iron'],
    },
    'turbid-patterned-crystal': {
        'name': '恶名狩猎 · 魇缚者·叶释渊',
        'category': '恶名狩猎',
        'type': '魇缚者·叶释渊',
        'mission': None,
        'cost': 60,
        'materials': ['turbid-patterned-crystal'],
    },
    'foul-red-crystal-spike': {
        'name': '恶名狩猎 · 彷徨猎手',
        'category': '恶名狩猎',
        'type': '彷徨猎手',
        'mission': None,
        'cost': 60,
        'materials': ['foul-red-crystal-spike'],
    },
}


def load(name: Any, file: Any) -> Any:
    return import_support(file)


def policy(root: Any = ROOT) -> Any:
    return load('zzz_stock_policy', Path(root) / 'tools/inventory-deficit-policy.py')


ROUTES.update(
    load('zzz_cultivation_families', ROOT / 'tools/inventory-zzz-families.py').routes()
)
ROUTES.update(
    load(
        'zzz_named_cultivation', ROOT / 'tools/inventory-zzz-families.py'
    ).named_routes()
)


def material_options(root: Any = ROOT) -> Any:
    cfg = load('zzz_stock_cfg', Path(root) / 'tools/inventory-task-config.py')
    plan = json.loads(
        cfg.config_path(root, 'zzz-inventory-task-plan.json').read_text(
            encoding='utf-8-sig'
        )
    )
    if (
        plan.get('schema') != 'inventory-inspection-plan/v1'
        or plan.get('game') != 'zzz'
        or plan.get('ready') is not True
        or (not isinstance(plan.get('pages'), list))
        or (not 1 <= len(plan['pages']) <= 128)
    ):
        raise ValueError('仓库识别计划尚未准备好')
    options, seen, loaded = ([], set(), {})
    for page in plan['pages']:
        name = page['calibration']
        if name not in loaded:
            loaded[name] = cfg.read_calibration(root, name, 'zzz')
        data = loaded[name]
        if data.get('game') != 'zzz' or data.get('ready') is not True:
            raise ValueError('材料标定尚未准备好')
        matches = [row for row in data['materials'] if row['id'] == page['material_id']]
        if len(matches) != 1 or page['material_id'] in seen:
            raise ValueError('材料标定身份重复或缺失')
        seen.add(page['material_id'])
        row = matches[0]
        if row['id'] in ROUTES:
            options.append({'id': row['id'], 'name': row['name'], 'route': row['id']})
    return options


def validate_targets(rows: Any, root: Any = ROOT) -> Any:
    result = policy(root).validate_plan(rows, ROUTES)
    options = {row['id']: row for row in material_options(root)}
    for row in result:
        if options.get(row['id']) != {key: row[key] for key in ('id', 'name', 'route')}:
            raise ValueError('此材料或刷取入口尚未接入库存识别')
    return result


def unavailable_materials(root: Any = ROOT) -> Any:
    """Explicit UI gaps, not selectable targets or inferred stock/route data."""
    root = Path(root)
    file = root / 'config/cultivation-required-materials.json'
    if file.stat().st_size > 2000000:
        raise ValueError('材料目录过大')
    observation = load('zzz_stock_required_display', root / 'inventory-observation.py')
    required = observation.required_materials(
        json.loads(file.read_text(encoding='utf-8-sig')), 'zzz'
    )
    options = material_options(root)
    for row in options:
        if row['id'] not in required or required[row['id']]['name'] != row['name']:
            raise ValueError('刷取选项与材料目录不一致')
    available = {row['id'] for row in options}
    return {
        'catalog_items': len(required),
        'available_items': len(available),
        'missing': [
            dict(row, quantity=None, target=None)
            for item_id, row in required.items()
            if item_id not in available
        ],
    }


class StockStore:
    """Account-specific JSON outside the upstream checkout. Fail closed on locks."""

    def __init__(self, instance_idx: Any, root: Any = ROOT) -> None:
        if type(instance_idx) is not int or not 0 <= instance_idx <= 99:
            raise ValueError('库存保持账号实例无效')
        self.instance_idx = instance_idx
        self.path = (
            Path(root) / 'config' / f'zzz-inventory-maintain-{instance_idx}.json'
        )

    def read(self) -> Any:
        if not self.path.exists():
            return {
                'schema': 'zzz-inventory-maintain/v1',
                'instance_idx': self.instance_idx,
                'targets': [],
                'pending': {},
                'history': {},
            }
        if self.path.stat().st_size > 2000000:
            raise ValueError('库存保持配置过大')
        data = json.loads(self.path.read_text(encoding='utf-8-sig'))
        if (
            data.get('schema') != 'zzz-inventory-maintain/v1'
            or data.get('instance_idx') != self.instance_idx
            or set(data) != {'schema', 'instance_idx', 'targets', 'pending', 'history'}
            or (not isinstance(data['targets'], list))
            or (not isinstance(data['pending'], dict))
            or (not isinstance(data['history'], dict))
        ):
            raise ValueError('库存保持配置或账号身份无效')
        return data

    def update(self, key: Any, value: Any) -> Any:
        if key not in ('targets', 'pending', 'history'):
            raise ValueError('不可修改库存身份字段')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix('.json.lock')
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        stage = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            data = self.read()
            data[key] = deepcopy(value)
            payload = json.dumps(
                data, ensure_ascii=False, indent=2, allow_nan=False
            ).encode('utf-8')
            if len(payload) > 2000000:
                raise ValueError('库存保持配置过大')
            with stage.open('xb') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(stage, self.path)
            if self.read().get(key) != value:
                raise RuntimeError('库存保持记录保存失败，不继续消耗电量')
        finally:
            stage.unlink(missing_ok=True)
            os.close(descriptor)
            lock.unlink()


class EphemeralChargePlan:
    """Minimum native ChargePlanConfig protocol; no YAML save/reset/refill."""

    loop = double_reward = skip_plan = daily_reset_plan_times = (
        is_restore_charge_enabled
    ) = False
    restore_charge = '不使用'

    def __init__(self, plan: Any) -> None:
        self.plan_list = [plan]

    def add_plan_run_times(self, plan: Any) -> Any:
        own = self.plan_list[0]
        if own.plan_id != plan.plan_id or own.run_times != 0:
            raise RuntimeError('库存保持原生计划尝试重复结算')
        own.run_times += 1

    def save(self) -> Any:
        pass

    def all_plan_finished(self) -> Any:
        return self.plan_list[0].run_times >= 1


class RunContextProxy:
    def __init__(self, original: Any, instance_idx: Any, config: Any) -> None:
        self.original, self.instance_idx, self.config = (original, instance_idx, config)
        self.hunt_record = EphemeralHuntRecord()

    def get_config(self, app_id: Any, instance_idx: Any, group_id: Any) -> Any:
        if app_id in ('charge_plan', 'notorious_hunt'):
            if instance_idx != self.instance_idx:
                raise RuntimeError('原生补刷计划请求了其他账号')
            return self.config
        return self.original.get_config(
            app_id=app_id, instance_idx=instance_idx, group_id=group_id
        )

    def get_run_record(self, app_id: Any, instance_idx: Any) -> Any:
        if app_id == 'notorious_hunt':
            if instance_idx != self.instance_idx:
                raise RuntimeError('原生周本请求了其他账号')
            return self.hunt_record
        return self.original.get_run_record(app_id=app_id, instance_idx=instance_idx)

    def __getattr__(self, key: Any) -> Any:
        return getattr(self.original, key)


class EphemeralHuntRecord:
    """Paid hunt never reads/writes/resets the production free-weekly record."""

    left_times = 0


class ContextProxy:
    def __init__(self, ctx: Any, config: Any) -> None:
        self.original = ctx
        self.run_context = RunContextProxy(
            ctx.run_context, ctx.current_instance_idx, config
        )
        if hasattr(ctx, 'compendium_service') and hasattr(
            ctx.compendium_service, 'data'
        ):
            registry = load(
                'stock_transport_extensions', ROOT / 'tools/inventory-zzz-families.py'
            )
            self.compendium_service = registry.extended_native_service(
                ctx.compendium_service
            )

    def __getattr__(self, key: Any) -> Any:
        return getattr(self.original, key)

    @property
    def notify_config(self) -> Any:
        return QuietNotifications(self.original.notify_config)


class QuietNotifications:
    enable_notify = False

    def __init__(self, original: Any) -> None:
        self.original = original

    def __getattr__(self, key: Any) -> Any:
        return getattr(self.original, key)


class GuardedController:
    """Guard native navigation AND the real auto-battle context's key presses.

    Key-up is allowed after focus loss, but a combined press/release still
    counts as input. A failed guard is latched: regaining focus never resumes
    a transaction that may already have consumed battery.
    """

    def __init__(self, original: Any, guard: Any) -> None:
        self.original, self.guard = (original, guard)
        self.failure, self.closed = (None, False)

    def check(self) -> Any:
        if self.closed or self.failure is not None:
            raise RuntimeError('库存保持输入已停止，不自动恢复') from self.failure
        try:
            self.guard()
        except Exception as exc:
            self.failure = exc
            raise

    def __getattr__(self, key: Any) -> Any:
        value = getattr(self.original, key)
        if not callable(value):
            return value

        def guarded(*args: Any, **kwargs: Any) -> Any:
            release_only = key in ('btn_release', 'stop_moving_forward')
            if key in (
                'dodge',
                'switch_next',
                'switch_prev',
                'switch_backup',
                'normal_attack',
                'special_attack',
                'ultimate',
                'chain_left',
                'chain_right',
                'move_w',
                'move_s',
                'move_a',
                'move_d',
                'interact',
                'lock',
                'chain_cancel',
            ):
                bound = inspect.signature(value).bind(*args, **kwargs)
                release_only = (
                    bound.arguments.get('release') is True
                    and bound.arguments.get('press', False) is False
                )
            if not release_only:
                self.check()
            return value(*args, **kwargs)

        return guarded


@contextmanager
def controller_scope(op: Any, guard: Any) -> Any:
    ctx, run = (op.ctx, op.ctx.run_context)
    owner, app_id = (run.current_application, run.current_app_id)
    original = ctx.controller
    proxy = GuardedController(original, guard)
    proxy.check()
    ctx.controller = proxy
    try:
        yield proxy.check
    finally:
        proxy.closed = True
        if ctx.controller is proxy:
            try:
                if run.current_application is owner and run.current_app_id == app_id:
                    ctx.auto_battle_context.stop_auto_battle()
            finally:
                ctx.controller = original


def make_guard(op: Any, manifest: Any) -> Any:
    import psutil
    import win32gui
    import win32process

    from zzz_od.application.inventory_inspection.inventory_inspection import (
        NativeVersions,
        lane_matches,
        load_module,
        native_window_identity,
    )

    owner = op.ctx.run_context.current_application
    bridge = load_module(
        'zzz_stock_guard_bridge', op.inventory_root / 'tools/inventory-task-session.py'
    )
    expected = native_window_identity(op.ctx.controller, psutil, win32gui, win32process)
    executable = expected['path']
    if not valid_game_path('zzz', executable):
        raise RuntimeError('原生窗口不是绝区零')
    if not bridge.same_identity(expected, dict(expected, path=executable)):
        raise RuntimeError('库存补刷窗口不是当前绝区零安装')
    versions = NativeVersions(bridge.probe, executable, 'zzz')
    expected_versions = deepcopy(versions())
    calibrated_versions = {
        key: manifest[key] for key in ('game_exe_sha256', 'resource_fingerprints')
    }
    if expected_versions != calibrated_versions:
        raise RuntimeError('库存标定与当前游戏版本不一致，不发送任何输入')
    deadline = time.monotonic() + 3600

    def guard() -> Any:
        if not lane_matches(op, owner) or time.monotonic() >= deadline:
            raise RuntimeError('库存补刷已停止、超时或执行权改变')
        current = native_window_identity(
            op.ctx.controller, psutil, win32gui, win32process
        )
        if (
            not bridge.same_identity(expected, current)
            or versions() != expected_versions
        ):
            raise RuntimeError('绝区零失去焦点、身份或资源版本改变，停止补刷')

    guard()
    return guard


def require_success(result: Any, label: Any) -> Any:
    if getattr(result, 'success', getattr(result, 'is_success', False)) is not True:
        raise RuntimeError(label + '未完成：' + str(result.status)[:160])


def natural_value(ocr: Any) -> Any:
    values = set()
    for text, matches in (ocr or {}).items():
        found = list(re.finditer('(?<![\\d.+−-])(\\d+)\\s*/\\s*240(?![\\d.])', text))
        for match in matches or []:
            if abs(match.x + match.w / 2 - 173) > 100:
                continue
            values.update(int(value.group(1)) for value in found)
    if len(values) != 1 or not 0 <= next(iter(values)) <= 240:
        raise RuntimeError('自然电量尚未识别，未知不当作0')
    return next(iter(values))


def read_natural(op: Any, guard: Any) -> Any:
    from zzz_od.operation.back_to_normal_world import BackToNormalWorld

    guard()
    require_success(
        BackToNormalWorld(op.ctx, ensure_normal_world=True).execute(), '返回大世界'
    )
    deadline = time.monotonic() + 60
    while True:
        guard()
        if time.monotonic() >= deadline:
            raise TimeoutError('打开快捷手册超时')
        result = op.round_by_goto_screen(
            screen=op.screenshot(), screen_name='快捷手册-训练', retry_wait=0.5
        )
        if result.is_success:
            break
        if result.is_fail:
            require_success(result, '打开快捷手册')
    values = []
    for _ in range(2):
        guard()
        frame = op.screenshot()
        scan = op.ctx.cv_service.run_pipeline('电量检测', frame)
        values.append(natural_value(scan.ocr_result))
        time.sleep(0.5)
    if not values[0] <= values[1] <= values[0] + 1:
        raise RuntimeError('自然电量两次读数不一致')
    return values[-1]


def build_plan(ctx: Any, route: Any) -> Any:
    from zzz_od.application.charge_plan.charge_plan_config import (
        ChargePlanConfig,
        ChargePlanItem,
    )

    category = route.get('category', '实战模拟室')
    if category not in ('实战模拟室', '专业挑战室', '恶名狩猎'):
        raise ValueError('尚未接入此材料副本类型')
    plan = ChargePlanItem(
        tab_name='训练',
        category_name=category,
        mission_type_name=route['type'],
        mission_name=route['mission'],
        card_num='1',
        plan_times=1,
        run_times=0,
        predefined_team_idx=-1,
        auto_battle_config='全配队通用',
        level='等级Lv.65' if category == '恶名狩猎' else '默认等级',
    )
    validation_ctx = ctx
    if hasattr(ctx, 'compendium_service') and hasattr(ctx.compendium_service, 'data'):
        registry = load(
            'stock_native_extensions', ROOT / 'tools/inventory-zzz-families.py'
        )
        validation_ctx = SimpleNamespace(
            compendium_service=registry.extended_native_service(ctx.compendium_service)
        )
    reason = ChargePlanConfig.validate_item(validation_ctx, plan)
    if reason:
        raise ValueError('原生材料入口已改变：' + reason)
    if plan.estimated_charge_power != route['cost']:
        raise ValueError('原生材料入口电量消耗已改变')
    return plan


def hunt_area_text(op: Any, frame: Any, area_name: Any) -> Any:
    """Read native named areas; one exact confident token, no digit tails."""
    area = op.ctx.screen_loader.get_area('恶名狩猎', area_name)
    if area is None:
        raise RuntimeError('原生恶名狩猎识别区域缺失')
    tokens = []
    for text, matches in op.ctx.ocr.crop_and_run_ocr(frame, area.rect).items():
        match = matches.max
        score = getattr(match, 'confidence', None)
        if (
            not isinstance(text, str)
            or isinstance(score, bool)
            or (not isinstance(score, (int, float)))
            or (not isfinite(score))
            or (not 0.9 <= score <= 1)
        ):
            raise RuntimeError('恶名狩猎入口文字尚未核实')
        tokens.append(''.join(text.split()))
    if len(tokens) != 1:
        raise RuntimeError('恶名狩猎入口文字缺失或重复')
    return tokens[0]


def verify_paid_hunt_entry(op: Any, guard: Any, before_paid: Any) -> Any:
    """Fresh boss/Lv65/ON/cost60/battery admission, never a spending receipt."""
    readings = []
    for index in range(2):
        guard()
        before_paid()
        frame = op.screenshot()
        if hunt_area_text(op, frame, '标题-副本名称') != op.plan.mission_type_name:
            raise RuntimeError('恶名狩猎首领名称不符，不消耗电量')
        level = hunt_area_text(op, frame, '难度选择入口')
        if not re.fullmatch('(?:等级)?[Ll][Vv][.．]65', level):
            raise RuntimeError('恶名狩猎Lv.65尚未核实，不消耗电量')
        if hunt_area_text(op, frame, '按钮-深度追猎-ON') != 'ON':
            raise RuntimeError('深度追猎尚未开启，不消耗电量')
        cost = hunt_area_text(op, frame, '文本-需要电量')
        if cost not in ('60', '/60'):
            raise RuntimeError('未确认单场60电量，不进入战斗')
        value = hunt_area_text(op, frame, '文本-剩余电量')
        if not re.fullmatch('\\d+', value) or not 60 <= int(value) <= 240:
            raise RuntimeError('自然电量不足或未核实，不进入战斗')
        readings.append(int(value))
        guard()
        if index == 0:
            time.sleep(0.15)
    if not readings[0] <= readings[1] <= readings[0] + 1:
        raise RuntimeError('恶名狩猎自然电量读数不一致')


def verify_free_hunt_refusal(op: Any, guard: Any, before_paid: Any) -> Any:
    """Native 'blocked' alone can mean a missing UI match, not positive quota."""
    readings = []
    for index in range(2):
        guard()
        before_paid()
        frame = op.screenshot()
        if hunt_area_text(op, frame, '标题-副本名称') != op.plan.mission_type_name:
            raise RuntimeError('跳过周本前首领名称未核实')
        if hunt_area_text(op, frame, '剩余奖励次数') != '剩余奖励次数':
            raise RuntimeError('免费周本次数标签未核实，不跳过')
        value = hunt_area_text(op, frame, '剩余次数')
        if not re.fullmatch('[1-3]', value):
            raise RuntimeError('免费周本剩余次数未核实，不跳过')
        readings.append(int(value))
        guard()
        if index == 0:
            time.sleep(0.15)
    if readings[0] != readings[1]:
        raise RuntimeError('免费周本剩余次数不一致，不跳过')


def verify_expert_entry(op: Any, guard: Any, before_paid: Any) -> Any:
    """Two fresh exact boss/cost/battery readings using native expert areas.

    This proves admission only, not a drop or a material-to-boss mapping.
    Do not borrow the hunt title rectangle: the expert screen only defines
    native battery areas, so require a unique full-frame exact boss token.
    """
    readings = []
    target = ''.join(op.plan.mission_type_name.split())
    for index in range(2):
        guard()
        before_paid()
        frame = op.screenshot()
        names = op.ctx.ocr.run_ocr(frame)
        matches = [
            match
            for text, values in names.items()
            if isinstance(text, str) and ''.join(text.split()) == target
            for match in values
        ]
        if len(matches) != 1:
            raise RuntimeError('专业挑战室首领名称未核实，不消耗电量')
        score = getattr(matches[0], 'confidence', None)
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or (not isfinite(score))
            or (not 0.9 <= score <= 1)
        ):
            raise RuntimeError('专业挑战室首领文字不清楚，不消耗电量')
        values = []
        for name in ('需要电量', '剩余电量'):
            area = op.ctx.screen_loader.get_area('专业挑战室', name)
            if area is None:
                raise RuntimeError('原生专业挑战室电量区域缺失')
            tokens = op.ctx.ocr.crop_and_run_ocr(frame, area.rect)
            if len(tokens) != 1 or len(next(iter(tokens.values()))) != 1:
                raise RuntimeError('专业挑战室电量读数缺失或重复')
            text, found = next(iter(tokens.items()))
            confidence = getattr(found.max, 'confidence', None)
            if (
                not isinstance(text, str)
                or isinstance(confidence, bool)
                or (not isinstance(confidence, (int, float)))
                or (not isfinite(confidence))
                or (not 0.9 <= confidence <= 1)
            ):
                raise RuntimeError('专业挑战室电量文字不清楚')
            values.append(''.join(text.split()))
        cost, battery = values
        if (
            cost not in ('40', '/40')
            or not re.fullmatch('\\d+', battery)
            or (not 40 <= int(battery) <= 240)
        ):
            raise RuntimeError('未确认单场40自然电量，不进入专业挑战室')
        readings.append(int(battery))
        guard()
        if index == 0:
            time.sleep(0.15)
    if not readings[0] <= readings[1] <= readings[0] + 1:
        raise RuntimeError('专业挑战室自然电量读数不一致')


def expert_battle(ctx: Any, plan: Any, guard: Any, before_paid: Any) -> Any:
    """One native ExpertChallenge; uncertain input is never retried.

    Selected routes have reviewed named-item/native-destination bindings.
    Stock recognition remains a trial: unknown counts never authorize input.
    """
    if (
        plan.category_name != '专业挑战室'
        or plan.mission_name is not None
        or plan.is_agent_plan
        or (type(plan.plan_times) is not int)
        or (plan.plan_times != 1)
        or (type(plan.run_times) is not int)
        or (plan.run_times != 0)
        or (plan.estimated_charge_power != 40)
    ):
        raise ValueError('专业挑战室只接受单场40电量的已核实原生计划')
    from one_dragon.base.operation.operation_edge import node_from
    from one_dragon.base.operation.operation_node import operation_node
    from zzz_od.operation.compendium.expert_challenge import ExpertChallenge
    from zzz_od.operation.deploy import Deploy

    class SingleDeploy(Deploy):
        def __init__(self) -> None:
            super().__init__(ctx)
            self.clicked = False

        @operation_node(name='出战', is_start_node=True, node_max_retry_times=0)
        def deploy(self) -> Any:
            guard()
            before_paid()
            if self.clicked:
                return self.round_fail('本场出战已尝试，不重复点击')
            self.clicked = True
            return self.round_by_find_and_click_area(
                self.last_screenshot, '通用-出战', '按钮-出战', success_wait=1
            )

    class SingleExpert(ExpertChallenge):
        def __init__(self) -> None:
            super().__init__(ctx, plan)
            self.next_attempted = self.start_attempted = False

        @node_from(from_name='关闭燃竭模式')
        @operation_node(name='下一步', node_max_retry_times=10)
        def click_next(self) -> Any:
            guard()
            before_paid()
            if self.next_attempted:
                return self.round_by_find_area(
                    self.last_screenshot, '实战模拟室', '出战', retry_wait=1
                )
            try:
                verify_expert_entry(self, guard, before_paid)
            except Exception as exc:
                return self.round_fail(str(exc)[:180])
            self.next_attempted = True
            result = self.round_by_find_and_click_area(
                self.last_screenshot, '实战模拟室', '下一步'
            )
            if not result.is_success:
                return self.round_fail('专业挑战室下一步未确认，停止，不重复点击')
            return self.round_wait(wait=0.5)

        @node_from(from_name='选择预备编队')
        @operation_node(name='出战', node_max_retry_times=0)
        def deploy(self) -> Any:
            guard()
            before_paid()
            if not self.next_attempted or self.start_attempted:
                return self.round_fail('本场入口未核实或已出战，不重复点击')
            self.start_attempted = True
            return self.round_by_op_result(SingleDeploy().execute())

        @node_from(from_name='自动战斗', status='普通战斗-撤退')
        @operation_node(name='战斗失败', node_max_retry_times=0)
        def battle_fail(self) -> Any:
            return self.round_fail('专业挑战室战斗失败，停止，不自动重刷')

        @node_from(from_name='出战')
        @operation_node(name='加载自动战斗指令')
        def init_auto_battle(self) -> Any:
            guard()
            if not self.start_attempted:
                return self.round_fail('专业挑战室尚未出战，不启动自动战斗')
            return super().init_auto_battle()

        @node_from(from_name='自动战斗')
        @operation_node(name='战斗结束', node_max_retry_times=0)
        def after_battle(self) -> Any:
            guard()
            if (
                not self.next_attempted
                or not self.start_attempted
                or self.ctx.auto_battle_context.last_check_end_result != '普通战斗-完成'
            ):
                return self.round_fail('专业挑战室胜利未核实，不结算计划')
            return super().after_battle()

        @node_from(from_name='战斗结束')
        @operation_node(name='判断下一次', node_max_retry_times=0)
        def check_next(self) -> Any:
            guard()
            if self.plan.run_times != 1 or self.plan.plan_times != 1:
                return self.round_fail('专业挑战室单场记录异常，不重复挑战')
            result = super().check_next()
            if result.status == '战斗结果-再来一次':
                return self.round_fail('库存保持只允许单场，不重复专业挑战室')
            return result

    return SingleExpert()


def native_battle(ctx: Any, plan: Any, route: Any, guard: Any, before_paid: Any) -> Any:
    """Reuse native battle graph, one paid entry, no free-weekly or refill path."""
    if route.get('category', '实战模拟室') == '实战模拟室':
        from zzz_od.operation.compendium.combat_simulation import CombatSimulation

        return CombatSimulation(ctx, plan)
    if route.get('category') == '专业挑战室':
        return expert_battle(ctx, plan, guard, before_paid)
    if route.get('category') != '恶名狩猎':
        raise ValueError('尚未接入此材料副本类型')
    from one_dragon.base.operation.operation_edge import node_from
    from one_dragon.base.operation.operation_node import operation_node
    from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt

    class SinglePaidHunt(NotoriousHunt):
        def __init__(self) -> None:
            super().__init__(ctx, plan, use_charge_power=True)
            self.paid_entry_attempted = self.start_attempted = False

        def _match_mission_type(self, target_name: Any, ocr_result: Any) -> Any:
            return ''.join(target_name.split()) == ''.join(ocr_result.split())

        @node_from(from_name='选择难度')
        @operation_node(name='下一步', node_max_retry_times=10)
        def click_next(self) -> Any:
            guard()
            before_paid()
            if not self.paid_entry_attempted:
                try:
                    verify_paid_hunt_entry(self, guard, before_paid)
                except Exception as exc:
                    return self.round_fail(str(exc)[:180])
                self.paid_entry_attempted = True
            return super().click_next()

        @node_from(from_name='选择预备编队')
        @operation_node(name='出战', node_max_retry_times=0)
        def click_start(self) -> Any:
            guard()
            before_paid()
            if not self.paid_entry_attempted or self.start_attempted:
                return self.round_fail('本场出战尚未核实或已尝试，不重复点击')
            self.start_attempted = True
            return super().click_start()

        @node_from(from_name='自动战斗', status='普通战斗-撤退')
        @operation_node(name='战斗失败', node_max_retry_times=0)
        def battle_fail(self) -> Any:
            return self.round_fail('材料周本战斗失败，停止，不自动倒带或重刷')

        @node_from(from_name='自动战斗')
        @operation_node(name='战斗结束', node_max_retry_times=0)
        def after_battle(self) -> Any:
            guard()
            if self.ctx.auto_battle_context.last_check_end_result != '普通战斗-完成':
                return self.round_fail('周本胜利尚未核实，不结算计划')
            return super().after_battle()

        @node_from(from_name='判断下一次', status='战斗结果-再来一次')
        @operation_node(name='重新开始-确认', node_max_retry_times=0)
        def restart_confirm(self) -> Any:
            return self.round_fail('库存保持只允许单场，不重复挑战')

    return SinglePaidHunt()


def farm_once(op: Any, store: Any, route: Any, guard: Any) -> Any:
    from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium

    plan = build_plan(op.ctx, route)
    config = EphemeralChargePlan(plan)
    ctx = ContextProxy(op.ctx, config)
    guard()
    pending = store.read()['pending']
    route_id = next((key for key, value in ROUTES.items() if value == route), None)
    if (
        not pending
        or pending.get('pending') is not True
        or route_id is None
        or (pending.get('route') != route_id)
        or (pending.get('cost') != route['cost'])
        or (pending.get('material_id') not in route['materials'])
    ):
        raise RuntimeError('本场缺少持久待核实记录，不消耗电量')
    category = route.get('category', '实战模拟室')

    def before_paid() -> Any:
        guard()
        if store.read()['pending'] != pending:
            raise RuntimeError('本场库存补刷记录改变，不消耗电量')

    battle = native_battle(ctx, plan, route, guard, before_paid)
    require_success(
        TransportByCompendium(ctx, '训练', category, route['type']).execute(),
        '前往材料副本',
    )
    guard()
    if store.read()['pending'] != pending:
        raise RuntimeError('本场库存补刷记录改变，不消耗电量')
    battle.timeout_seconds = 900
    result = battle.execute()
    if (
        category == '恶名狩猎'
        and getattr(result, 'success', False) is True
        and (result.status == battle.STATUS_BLOCKED_BY_LEFT_TIMES)
        and (battle.paid_entry_attempted is False)
        and (battle.start_attempted is False)
        and (type(plan.run_times) is int)
        and (plan.run_times == 0)
    ):
        before_paid()
        verify_free_hunt_refusal(battle, guard, before_paid)
        return {'state': 'route_unavailable', 'reason': 'free_weekly_quota_remaining'}
    require_success(result, '材料战斗')
    guard()
    if (
        plan.run_times != 1
        or op.ctx.auto_battle_context.last_check_end_result != '普通战斗-完成'
    ):
        raise RuntimeError('未核实单场战斗胜利，保留待核实记录，不重刷')


def run_maintain(op: Any) -> Any:
    from zzz_od.application.inventory_inspection.inventory_inspection import (
        load_module,
        prepare,
        run_inventory_inspection,
    )

    store = StockStore(op.ctx.current_instance_idx, op.inventory_root)
    saved = store.read()
    rows = validate_targets(saved['targets'], op.inventory_root)
    if saved['pending']:
        raise RuntimeError('上次补刷扣电量尚未核实，请先检查日志；不会自动重刷')
    stock_policy = policy(op.inventory_root)
    conversion_families = stock_policy.equivalence.load_families(
        op.inventory_root, 'zzz'
    )
    ids = [
        row['id']
        for row in stock_policy.equivalence.observation_rows(rows, conversion_families)
    ]
    bridge = load_module(
        'zzz_stock_preflight_bridge',
        op.inventory_root / 'tools/inventory-task-session.py',
    )
    navigation = load_module(
        'zzz_stock_preflight_nav',
        op.inventory_root / 'tools/inventory-native-navigation.py',
    )
    _, _, manifest = prepare(op.inventory_root, bridge, navigation, ids)
    for row in rows:
        build_plan(op.ctx, ROUTES[row['route']])
    guard = make_guard(op, manifest)

    def inspect() -> Any:
        guard()
        from zzz_od.operation.back_to_normal_world import BackToNormalWorld

        require_success(
            BackToNormalWorld(op.ctx, ensure_normal_world=True).execute(), '返回大世界'
        )
        report = run_inventory_inspection(op, op.inventory_root, selected_ids=ids)
        store.update(
            'history',
            {
                'observed_at': datetime.now(UTC).isoformat(),
                'materials': [
                    {key: row.get(key) for key in ('id', 'name', 'quantity', 'status')}
                    for row in report['materials']
                    if row.get('id') in ids
                ],
            },
        )
        return report

    with controller_scope(op, guard) as owned_guard:
        guard = owned_guard
        result = policy(op.inventory_root).run_cycle(
            rows,
            ROUTES,
            game='zzz',
            inspect=inspect,
            read_stamina=lambda: read_natural(op, guard),
            farm_once=lambda row, route: farm_once(op, store, route, guard),
            journal=lambda record: store.update('pending', record),
            pending=saved['pending'],
            guard=guard,
            conversion_families=conversion_families,
        )
    from one_dragon.utils.log_utils import log

    log.info('InventoryMaintain/v1 %s', json.dumps(result, ensure_ascii=False))
    if result['state'] == 'run_budget_reached':
        raise RuntimeError('达到本次场数上限，材料尚未全部达标')
    return result


def application_type(Application: Any, operation_node: Any) -> Any:

    class InventoryMaintainApplication(Application):
        """按列表顺序补齐养成材料；达标或自然电量不足即结束，不恢复电量。"""

        def __init__(self, ctx: Any, root: Any = ROOT) -> None:
            self.inventory_root = Path(root).resolve(strict=True)
            Application.__init__(
                self,
                ctx=ctx,
                app_id=APP_ID,
                op_name='库存保持',
                need_check_game_win=False,
                op_to_enter_game=None,
                node_max_retry_times=0,
                timeout_seconds=3600,
            )
            self.run_record = None

        @operation_node(
            name='按库存补刷',
            is_start_node=True,
            node_max_retry_times=0,
            screenshot_before_round=False,
        )
        def maintain(self) -> Any:
            try:
                result = run_maintain(self)
                if result.get('unavailable'):
                    return self.round_fail(
                        status='免费周本次数尚未用完，相关材料已跳过；库存未全部达标',
                        data=result,
                    )
                status = (
                    '目标已达标'
                    if result['state'] == 'targets_met'
                    else '自然电量不足，已结束'
                )
                if result['state'] == 'targets_met' and any(
                    f['requires_conversion'] for f in result['equivalence']['families']
                ):
                    status = '折算已够用，使用前请合成或分解'
                elif result['state'] == 'targets_met' and any(
                    f['requires_substitution']
                    for f in result['equivalence']['families']
                ):
                    status = '经验总量已够用，不再补刷'
                return self.round_success(status=status, data=result)
            except Exception as exc:
                return self.round_fail(status='库存保持未完成：' + str(exc)[:240])

    return InventoryMaintainApplication
