"""Config 修改路由表:app_id → 领域方法 / 校验 / 写穿取 config。

通用 MCP 入口(set/add/update/delete_config_item)按 app_id 路由到各 config 的领域方法,
**不裸写 data**(覆写 save() 的 config 会丢写)。handler 写穿 ctx 内同一缓存实例
(经 run_context.get_config 等),写入前校验,不合法拒绝。

详见 `docs/superpowers/specs/2026-07-24-mcp-config-design.md`(v5)。

v1 最小闭环:charge_plan plan_list add/delete。
"""
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


@dataclass
class RouterEntry:
    """单个 app config 的路由条目。

    各 callable 延迟 import(避免循环):
    - ``item_from_dict``:dict → 数据类 item(经 from_dict)
    - ``get_config``:(ctx, instance_idx, group_id) → 写穿 ctx 内**同一缓存** config 实例
    - ``validate_item``:(ctx, item) → str | None(合法 None / 非法返原因)
    - ``add``:(config, item) → 领域方法(如 add_plan,内部 save)
    - ``delete``:(config, id) → 领域方法;id 按 ``id_kind`` 解析
    """

    app_id: str
    item_from_dict: Callable[[dict], object]
    get_config: Callable[['ZContext', int | None, str | None], object]
    validate_item: Callable[['ZContext', object], str | None]
    add: Callable[[object, object], None]
    delete: Callable[[object, str], bool]
    id_kind: str  # 'plan_id' / 'idx' / 'app_id'


def _charge_plan_get_config(
    ctx: 'ZContext', instance_idx: int | None, group_id: str | None,
) -> object:
    """写穿:经 run_context.get_config 拿 factory._config_cache 同一实例。"""
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
    """plan_id → idx(领域方法 delete_plan 收 idx)。"""
    for i, p in enumerate(config.plan_list):  # type: ignore[attr-defined]
        if p.plan_id == plan_id:
            config.delete_plan(i)  # type: ignore[attr-defined]
            return True
    return False


def _notorious_hunt_get_config(
    ctx: 'ZContext', instance_idx: int | None, group_id: str | None,
) -> object:
    """写穿:经 run_context.get_config 拿 factory._config_cache 同一实例。"""
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


def _standalone_app_get_config(
    ctx: 'ZContext', instance_idx: int | None, group_id: str | None,
) -> object:
    """写穿:standalone_app_config 是 @cached_property(绑定 current_instance_idx)。"""
    return ctx.standalone_app_config


def _standalone_app_item_from_dict(data: dict) -> str:
    """standalone_app 的 item 是 app_id 字符串(非 dataclass)。"""
    return data.get('app_id', '')


def _standalone_app_validate_item(ctx: 'ZContext', item: str) -> str | None:
    if not ctx.run_context.is_app_registered(item):
        return f'app_id {item} 未注册(不在应用列表)'
    return None


def _standalone_app_add(config: object, item: str) -> None:
    """read-modify-write 经 setter(直接改 list 不落盘)。"""
    config.app_list = config.app_list + [item]  # type: ignore[attr-defined]


def _standalone_app_delete(config: object, item: str) -> bool:
    old_len = len(config.app_list)  # type: ignore[attr-defined]
    config.app_list = [a for a in config.app_list if a != item]  # type: ignore[attr-defined]
    return len(config.app_list) < old_len  # type: ignore[attr-defined]


def _group_get_config(
    ctx: 'ZContext', instance_idx: int | None, group_id: str | None,
) -> object:
    """写穿:经 app_group_manager.get_one_dragon_group_config 拿同一缓存实例。"""
    idx = instance_idx if instance_idx is not None else ctx.current_instance_idx
    return ctx.app_group_manager.get_one_dragon_group_config(idx)


def _group_validate_item(ctx: 'ZContext', item: str) -> str | None:
    if not ctx.run_context.is_app_registered(item):
        return f'app_id {item} 未注册(不在应用列表)'
    return None


def _group_add(_config: object, _item: str) -> None:
    """_group 不支持 add(app 由注册注入,无 add_app 领域方法)。"""
    raise ValueError('_group 不支持 add(app 由注册注入)')


def _group_delete(config: object, app_id: str) -> bool:
    for item in config._all_apps:  # type: ignore[attr-defined]
        if item.app_id == app_id:  # type: ignore[attr-defined]
            config.remove_app(app_id)  # type: ignore[attr-defined]
            return True
    return False


ROUTES: dict[str, RouterEntry] = {
    'charge_plan': RouterEntry(
        app_id='charge_plan',
        item_from_dict=_charge_plan_item_from_dict,
        get_config=_charge_plan_get_config,
        validate_item=_charge_plan_validate_item,
        add=_charge_plan_add,
        delete=_charge_plan_delete,
        id_kind='plan_id',
    ),
    'notorious_hunt': RouterEntry(
        app_id='notorious_hunt',
        item_from_dict=_charge_plan_item_from_dict,
        get_config=_notorious_hunt_get_config,
        validate_item=_notorious_hunt_validate_item,
        add=_charge_plan_add,
        delete=_charge_plan_delete,
        id_kind='plan_id',
    ),
    'standalone_app': RouterEntry(
        app_id='standalone_app',
        item_from_dict=_standalone_app_item_from_dict,
        get_config=_standalone_app_get_config,
        validate_item=_standalone_app_validate_item,
        add=_standalone_app_add,
        delete=_standalone_app_delete,
        id_kind='app_id',
    ),
    '_group': RouterEntry(
        app_id='_group',
        item_from_dict=_standalone_app_item_from_dict,
        get_config=_group_get_config,
        validate_item=_group_validate_item,
        add=_group_add,
        delete=_group_delete,
        id_kind='app_id',
    ),
}


def get_entry(app_id: str) -> RouterEntry | None:
    """按 app_id 取路由条目;未注册返 None(handler 拒绝)。"""
    return ROUTES.get(app_id)
