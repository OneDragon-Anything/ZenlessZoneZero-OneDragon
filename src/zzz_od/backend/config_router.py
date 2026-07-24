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
}


def get_entry(app_id: str) -> RouterEntry | None:
    """按 app_id 取路由条目;未注册返 None(handler 拒绝)。"""
    return ROUTES.get(app_id)
