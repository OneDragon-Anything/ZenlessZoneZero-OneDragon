"""Config 修改路由表:app_id → 领域方法 / 校验 / 写穿取 config / describe schema。

通用 MCP 入口(set/add/update/delete/describe_config_item)按 app_id 路由到各 config 的领域方法,
**不裸写 data**(覆写 save() 的 config 会丢写)。handler 写穿 ctx 内同一缓存实例
(经 run_context.get_config 等),写入前校验,不合法拒绝。

详见 `docs/superpowers/specs/2026-07-24-mcp-config-design.md`(v5) +
`docs/superpowers/specs/2026-07-25-mcp-config-describe-design.md`(v5)。
"""
from collections.abc import Callable
from dataclasses import dataclass, fields as dataclass_fields
from enum import Enum
from typing import TYPE_CHECKING, Any

from one_dragon.base.config.config_item import ConfigItem

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


# === RouterEntry ===

@dataclass
class RouterEntry:
    """单个 app config 的路由条目。

    各 callable 延迟 import(避免循环)。
    field_schema / item_schema 集中声明(不散落 config 类)。
    """

    app_id: str
    description: str
    item_from_dict: Callable[[dict], object]
    get_config: Callable[['ZContext', int | None, str | None], object]
    validate_item: Callable[['ZContext', object], str | None]
    add: Callable[[object, object], None]
    delete: Callable[[object, str], bool]
    id_kind: str  # 'plan_id' / 'idx' / 'app_id'
    item_kind: str = 'dataclass'  # 'dataclass' / 'str' / 'dict'
    supported_ops: tuple[str, ...] = ('get', 'set', 'add', 'delete', 'describe')
    field_schema: dict[str, dict] | None = None
    item_schema: list[dict] | None = None


# === Enum 反射 helper ===

def _enum_options(enum_cls: type[Enum]) -> list[dict]:
    """从 Enum 类反射 options: [{label, value}]。value = ConfigItem.value(智能体传这个)。"""
    return [
        {'label': m.value.label, 'value': m.value.value}
        for m in enum_cls
        if isinstance(m.value, ConfigItem)
    ]


# === describe schema 组装 helper ===

def _build_set_fields(
    config: object, field_schema: dict[str, dict] | None, ro_fields: set[str] | None,
) -> list[dict]:
    """组装 set_fields(可改字段:name + type + value + options + desc)。

    从 field_schema 声明取 type/enum/desc;从 config.data 取当前值。
    只读字段(_RO_FIELDS)排除。
    """
    if field_schema is None:
        return []
    ro = ro_fields or set()
    result: list[dict] = []
    for name, meta in field_schema.items():
        if name in ro:
            continue
        field: dict[str, Any] = {
            'name': name,
            'type': meta.get('type', 'str'),
            'value': getattr(config, name, None) if not isinstance(getattr(config, name, None), property) else config.data.get(name),  # type: ignore[attr-defined]
            'desc': meta.get('desc', ''),
        }
        if meta.get('type') == 'enum' and 'enum_cls' in meta:
            field['options'] = _enum_options(meta['enum_cls'])
        elif 'options_source' in meta:
            field['note'] = f"合法值来源: {meta['options_source']}"
        result.append(field)
    return result


def _build_list_fields(
    entry: 'RouterEntry', ro_item_fields: list[str] | None,
) -> list[dict]:
    """组装 list_fields(item 结构 + add_example)。

    item_schema 优先(提供 enum/options/applicability/note);反射补 name+default。
    add_example 过滤 ro_item_fields。enum_cls 展开为 options。
    """
    if entry.item_schema is None:
        return []

    # 深拷贝 item_schema 并展开 enum_cls → options
    expanded_fields: list[dict] = []
    for f in entry.item_schema:
        ef = dict(f)
        if 'enum_cls' in ef:
            enum_cls = ef.pop('enum_cls')
            if isinstance(enum_cls, type) and issubclass(enum_cls, Enum):
                ef['options'] = _enum_options(enum_cls)
            elif isinstance(enum_cls, str):
                ef['options_source'] = enum_cls  # '从 compendium 取' 等描述
        expanded_fields.append(ef)

    # add_example: 从 expanded_fields 构造最小 dict(过滤 ro)
    ro = set(ro_item_fields or [])
    example: dict[str, Any] = {}
    for f in expanded_fields:
        if f['name'] in ro:
            continue
        if f.get('required') or 'default' in f:
            example[f['name']] = f.get('default', '')

    return [{
        'name': 'plan_list' if entry.item_kind == 'dataclass' else 'app_list',
        'id_kind': entry.id_kind,
        'id_source': f"get_config 读 list.{entry.id_kind}(add 时自动生成,不要传)" if entry.id_kind == 'plan_id' else f"get_config 读 list",
        'item_kind': entry.item_kind,
        'item_fields': expanded_fields,
        'note': '未列字段(tab_name 等)由 dataclass 默认值自动补,add 时可不传',
        'ro_item_fields': ro_item_fields or [],
        'add_example': example,
        'validate_hint': _validate_hint_for(entry.app_id),
    }]


def _validate_hint_for(app_id: str) -> str:
    """各 config 的校验提示。"""
    hints = {
        'charge_plan': 'category/mission_type/mission_name 必须在 compendium 合法;card_num 仅实战模拟室',
        'notorious_hunt': 'mission_type 必须在 compendium(恶名狩猎域)合法',
        'standalone_app': 'app_id 必须已注册(is_app_registered)',
        '_group': 'app_id 必须已注册;add 不支持(app 由注册注入)',
    }
    return hints.get(app_id, '')


def _ro_item_fields_for(app_id: str) -> list[str]:
    """各 config 的 item 级只读字段。"""
    if app_id in ('charge_plan',):
        return ['plan_id', 'skipped']
    if app_id in ('notorious_hunt',):
        return ['plan_id']
    return []


# === charge_plan helpers ===

def _charge_plan_get_config(
    ctx: 'ZContext', instance_idx: int | None, group_id: str | None,
) -> object:
    from one_dragon.base.operation.application import application_const
    from zzz_od.application.charge_plan import charge_plan_const

    idx = instance_idx if instance_idx is not None else ctx.current_instance_idx
    gid = group_id if group_id is not None else application_const.DEFAULT_GROUP_ID
    return ctx.run_context.get_config(
        app_id=charge_plan_const.APP_ID, instance_idx=idx, group_id=gid,
    )


def _charge_plan_item_from_dict(data: dict) -> object:
    from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
    return ChargePlanItem.from_dict(data)


def _charge_plan_validate_item(ctx: 'ZContext', item: object) -> str | None:
    from zzz_od.application.charge_plan.charge_plan_config import ChargePlanConfig
    return ChargePlanConfig.validate_item(ctx, item)


def _charge_plan_add(config: object, item: object) -> None:
    config.add_plan(item)  # type: ignore[attr-defined]


def _charge_plan_delete(config: object, plan_id: str) -> bool:
    for i, p in enumerate(config.plan_list):  # type: ignore[attr-defined]
        if p.plan_id == plan_id:
            config.delete_plan(i)  # type: ignore[attr-defined]
            return True
    return False


# === notorious_hunt helpers ===

def _notorious_hunt_get_config(
    ctx: 'ZContext', instance_idx: int | None, group_id: str | None,
) -> object:
    from one_dragon.base.operation.application import application_const
    from zzz_od.application.notorious_hunt import notorious_hunt_const

    idx = instance_idx if instance_idx is not None else ctx.current_instance_idx
    gid = group_id if group_id is not None else application_const.DEFAULT_GROUP_ID
    return ctx.run_context.get_config(
        app_id=notorious_hunt_const.APP_ID, instance_idx=idx, group_id=gid,
    )


def _notorious_hunt_validate_item(ctx: 'ZContext', item: object) -> str | None:
    from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntConfig
    return NotoriousHuntConfig.validate_item(ctx, item)


# === standalone_app helpers ===

def _standalone_app_get_config(
    ctx: 'ZContext', instance_idx: int | None, group_id: str | None,
) -> object:
    return ctx.standalone_app_config


def _standalone_app_item_from_dict(data: dict) -> str:
    return data.get('app_id', '')


def _standalone_app_validate_item(ctx: 'ZContext', item: str) -> str | None:
    if not ctx.run_context.is_app_registered(item):
        return f'app_id {item} 未注册(不在应用列表)'
    return None


def _standalone_app_add(config: object, item: str) -> None:
    config.app_list = config.app_list + [item]  # type: ignore[attr-defined]


def _standalone_app_delete(config: object, item: str) -> bool:
    old_len = len(config.app_list)  # type: ignore[attr-defined]
    config.app_list = [a for a in config.app_list if a != item]  # type: ignore[attr-defined]
    return len(config.app_list) < old_len  # type: ignore[attr-defined]


# === _group helpers ===

def _group_get_config(
    ctx: 'ZContext', instance_idx: int | None, group_id: str | None,
) -> object:
    idx = instance_idx if instance_idx is not None else ctx.current_instance_idx
    return ctx.app_group_manager.get_one_dragon_group_config(idx)


def _group_validate_item(ctx: 'ZContext', item: str) -> str | None:
    if not ctx.run_context.is_app_registered(item):
        return f'app_id {item} 未注册(不在应用列表)'
    return None


def _group_add(_config: object, _item: str) -> None:
    raise ValueError('_group 不支持 add(app 由注册注入)')


def _group_delete(config: object, app_id: str) -> bool:
    for item in config._all_apps:  # type: ignore[attr-defined]
        if item.app_id == app_id:  # type: ignore[attr-defined]
            config.remove_app(app_id)  # type: ignore[attr-defined]
            return True
    return False


# === ROUTES(含 field_schema + item_schema) ===

def _build_routes() -> dict[str, RouterEntry]:
    """延迟构建 ROUTES(enum_cls 需要 import,避免模块级循环)。"""
    from zzz_od.application.charge_plan.charge_plan_config import (
        CardNumEnum,
        RestoreChargeEnum,
    )
    from zzz_od.application.notorious_hunt.notorious_hunt_config import (
        NotoriousHuntBuffEnum,
        NotoriousHuntLevelEnum,
        NotoriousHuntWeekdayEnum,
    )

    return {
        'charge_plan': RouterEntry(
            app_id='charge_plan',
            description='体力计划配置',
            item_from_dict=_charge_plan_item_from_dict,
            get_config=_charge_plan_get_config,
            validate_item=_charge_plan_validate_item,
            add=_charge_plan_add,
            delete=_charge_plan_delete,
            id_kind='plan_id',
            item_kind='dataclass',
            supported_ops=('get', 'set', 'add', 'delete', 'describe'),
            field_schema={
                'loop': {'type': 'bool', 'desc': '循环执行'},
                'restore_charge': {'type': 'enum', 'enum_cls': RestoreChargeEnum, 'desc': '恢复电量方式'},
                'double_reward': {'type': 'bool', 'desc': '双倍活动'},
                'daily_reset_plan_times': {'type': 'bool', 'desc': '每日重置'},
            },
            item_schema=[
                {'name': 'category_name', 'type': 'enum', 'required': True, 'enum_cls': '从 compendium 取(charge_plan category: 实战模拟室/区域巡防/专业挑战室/恶名狩猎/定期清剿/合成电池)'},
                {'name': 'mission_type_name', 'type': 'str', 'required': True, 'note': '合法值依赖 category,describe_config 传 category 参数查'},
                {'name': 'mission_name', 'type': 'str', 'required': False, 'note': '部分 category/mission_type 必填(如实战模拟室/基础材料 需要传)'},
                {'name': 'plan_times', 'type': 'int', 'required': False, 'default': 1},
                {'name': 'run_times', 'type': 'int', 'required': False, 'default': 0, 'note': '运行次数(可手工修正,如手工跑了一次后调整)'},
                {'name': 'auto_battle_config', 'type': 'str', 'required': False, 'default': '全配队通用'},
                {'name': 'predefined_team_idx', 'type': 'int', 'required': False, 'default': -1},
                {'name': 'card_num', 'type': 'enum', 'required': False, 'enum_cls': CardNumEnum, 'applicability': '仅实战模拟室'},
                {'name': 'level', 'type': 'str', 'required': False, 'default': '默认等级'},
            ],
        ),
        'notorious_hunt': RouterEntry(
            app_id='notorious_hunt',
            description='恶名狩猎配置',
            item_from_dict=_charge_plan_item_from_dict,
            get_config=_notorious_hunt_get_config,
            validate_item=_notorious_hunt_validate_item,
            add=_charge_plan_add,
            delete=_charge_plan_delete,
            id_kind='plan_id',
            item_kind='dataclass',
            supported_ops=('get', 'set', 'add', 'delete', 'describe'),
            field_schema={
                'loop': {'type': 'bool', 'desc': '循环执行'},
                'weekly_challenge_start_weekday': {'type': 'enum', 'enum_cls': NotoriousHuntWeekdayEnum, 'desc': '周挑战起始日'},
            },
            item_schema=[
                {'name': 'category_name', 'type': 'enum', 'required': True, 'note': '固定恶名狩猎'},
                {'name': 'mission_type_name', 'type': 'str', 'required': True, 'note': '从 compendium 取(恶名狩猎域)'},
                {'name': 'mission_name', 'type': 'str', 'required': False, 'note': '常为 None'},
                {'name': 'level', 'type': 'enum', 'required': False, 'enum_cls': NotoriousHuntLevelEnum, 'default': '默认等级'},
                {'name': 'plan_times', 'type': 'int', 'required': False, 'default': 1},
                {'name': 'run_times', 'type': 'int', 'required': False, 'default': 0, 'note': '运行次数(可手工修正)'},
                {'name': 'auto_battle_config', 'type': 'str', 'required': False, 'default': '全配队通用'},
                {'name': 'predefined_team_idx', 'type': 'int', 'required': False, 'default': -1},
                {'name': 'notorious_hunt_buff_num', 'type': 'enum', 'required': False, 'enum_cls': NotoriousHuntBuffEnum, 'default': 1},
            ],
        ),
        'standalone_app': RouterEntry(
            app_id='standalone_app',
            description='独立应用列表',
            item_from_dict=_standalone_app_item_from_dict,
            get_config=_standalone_app_get_config,
            validate_item=_standalone_app_validate_item,
            add=_standalone_app_add,
            delete=_standalone_app_delete,
            id_kind='app_id',
            item_kind='str',
            supported_ops=('get', 'set', 'add', 'delete', 'describe'),
            field_schema={
                'active_app_id': {'type': 'str', 'desc': '当前激活的独立应用', 'options_source': 'config.app_list(动态,先 get_config 读)'},
            },
            item_schema=[
                {'name': 'app_id', 'type': 'str', 'required': True, 'note': '必须已注册(is_app_registered)'},
            ],
        ),
        '_group': RouterEntry(
            app_id='_group',
            description='一条龙应用组',
            item_from_dict=_standalone_app_item_from_dict,
            get_config=_group_get_config,
            validate_item=_group_validate_item,
            add=_group_add,
            delete=_group_delete,
            id_kind='app_id',
            item_kind='dict',
            supported_ops=('get', 'delete', 'describe'),
            item_schema=[
                {'name': 'app_id', 'type': 'str', 'required': True, 'note': '必须已注册'},
                {'name': 'enabled', 'type': 'bool', 'required': False, 'note': '经 set_app_enable 改,v1 无 MCP 入口'},
            ],
        ),
    }


_ROUTES: dict[str, RouterEntry] | None = None


def _routes() -> dict[str, RouterEntry]:
    """延迟初始化 ROUTES(避免模块级 import 循环)。"""
    global _ROUTES
    if _ROUTES is None:
        _ROUTES = _build_routes()
    return _ROUTES


def get_entry(app_id: str) -> RouterEntry | None:
    """按 app_id 取路由条目;未注册返 None(handler 拒绝)。"""
    return _routes().get(app_id)


def all_entries() -> dict[str, RouterEntry]:
    """返回全部路由(供 list_app_configs 遍历)。"""
    return _routes()
