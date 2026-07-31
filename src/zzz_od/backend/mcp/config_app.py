"""MCP 配置修改工具:通用入口 + app_id 路由到领域方法(写穿 ctx + 校验前置)。

详见 `docs/superpowers/specs/2026-07-24-mcp-config-design.md`(v5) +
`docs/superpowers/specs/2026-07-25-mcp-config-describe-design.md`(v5)。
"""
from collections.abc import Callable
from typing import Annotated, Any

from pydantic import Field

from zzz_od.backend.backend_context import ZzzBackendContext
from zzz_od.backend.config_router import (
    RouterEntry,
    _build_list_fields,
    _build_set_fields,
    _enum_options,
    _ro_item_fields_for,
    all_entries,
    get_entry,
)


def make_add_config_item(backend: ZzzBackendContext) -> Callable:
    """构造 ``add_config_item`` tool。"""
    async def add_config_item(
        app_id: Annotated[str, Field(description="app 配置 id,如 charge_plan")],
        list_field: Annotated[str, Field(description="列表字段名(plan_list/app_list)")],
        item_dict: Annotated[dict, Field(description="列表项 dict(经 from_dict 反序列化)")],
        instance_idx: Annotated[int | None, Field(description="实例 idx(idx N→config/0N:idx 1→config/01 账号01;None=当前实例)")] = None,
        group_id: Annotated[str | None, Field(description="组 id;None=默认组")] = None,
    ) -> dict:
        """加一个数据类列表项(如 charge_plan plan / standalone_app app)。操作类,改配置。

        通用入口,按 ``app_id`` 路由到该 config 的领域方法。写入前校验,不合法拒绝。
        改配置前建议先调 ``describe_config`` 查字段结构、合法值与只读项。
        """
        ctx = backend.ctx
        entry = get_entry(app_id)
        if entry is None:
            return {'ok': False, 'error': f'不支持的 app_id: {app_id}'}
        expected_list = 'plan_list' if entry.item_kind == 'dataclass' else 'app_list'
        if list_field != expected_list:
            return {'ok': False, 'error': f'list_field 应为 {expected_list},实际 {list_field}'}
        try:
            config = entry.get_config(ctx, instance_idx, group_id)
            item = entry.item_from_dict(item_dict)
            err = entry.validate_item(ctx, item)
            if err:
                return {'ok': False, 'error': err}
            entry.add(config, item)
            new_id: str | None = None
            if hasattr(config, 'plan_list') and config.plan_list:
                new_id = config.plan_list[-1].plan_id
            elif entry.id_kind == 'app_id' and isinstance(item, str):
                new_id = item
            return {'ok': True, 'app_id': app_id, 'list_field': list_field, 'id': new_id}
        except Exception as e:  # noqa: BLE001
            return {'ok': False, 'error': str(e)}
    return add_config_item


def make_delete_config_item(backend: ZzzBackendContext) -> Callable:
    """构造 ``delete_config_item`` tool。"""
    async def delete_config_item(
        app_id: Annotated[str, Field(description="app 配置 id,如 charge_plan")],
        list_field: Annotated[str, Field(description="列表字段名")],
        item_id: Annotated[str, Field(description="项标识:charge_plan/notorious_hunt 用 plan_id;standalone_app/_group 用 app_id")],
        instance_idx: Annotated[int | None, Field(description="实例 idx(idx N→config/0N:idx 1→config/01 账号01;None=当前实例)")] = None,
        group_id: Annotated[str | None, Field(description="组 id;None=默认组")] = None,
    ) -> dict:
        """删一个数据类列表项。操作类,改配置,可逆性低。

        改配置前建议先调 ``describe_config`` 查字段结构、合法值与只读项。
        """
        ctx = backend.ctx
        entry = get_entry(app_id)
        if entry is None:
            return {'ok': False, 'error': f'不支持的 app_id: {app_id}'}
        expected_list = 'plan_list' if entry.item_kind == 'dataclass' else 'app_list'
        if list_field != expected_list:
            return {'ok': False, 'error': f'list_field 应为 {expected_list},实际 {list_field}'}
        try:
            config = entry.get_config(ctx, instance_idx, group_id)
            deleted = entry.delete(config, item_id)
            if not deleted:
                return {'ok': False, 'error': f'未找到 id={item_id}'}
            return {'ok': True, 'app_id': app_id, 'list_field': list_field, 'id': item_id}
        except Exception as e:  # noqa: BLE001
            return {'ok': False, 'error': str(e)}
    return delete_config_item


def make_get_config(backend: ZzzBackendContext) -> Callable:
    """构造 ``get_config`` tool(读配置字段/全 data)。"""
    async def get_config(
        app_id: Annotated[str, Field(description="app 配置 id,如 charge_plan")],
        key: Annotated[str | None, Field(description="字段名;None=返全 data")] = None,
        instance_idx: Annotated[int | None, Field(description="实例 idx(idx N→config/0N:idx 1→config/01 账号01;None=当前)")] = None,
        group_id: Annotated[str | None, Field(description="组 id;None=默认")] = None,
    ) -> dict:
        """读配置字段或全部 data。观察类,不改配置。

        改配置前建议先调 ``describe_config`` 查字段结构、合法值与只读项。
        """
        ctx = backend.ctx
        entry = get_entry(app_id)
        if entry is None:
            return {'ok': False, 'error': f'不支持的 app_id: {app_id}'}
        try:
            config = entry.get_config(ctx, instance_idx, group_id)
            if key:
                return {'ok': True, 'app_id': app_id, 'key': key, 'value': config.data.get(key)}
            return {'ok': True, 'app_id': app_id, 'data': dict(config.data)}
        except Exception as e:  # noqa: BLE001
            return {'ok': False, 'error': str(e)}
    return get_config


def make_set_config(backend: ZzzBackendContext) -> Callable:
    """构造 ``set_config`` tool(写简单/enum 字段 + 校验只读)。"""
    async def set_config(
        app_id: Annotated[str, Field(description="app 配置 id,如 charge_plan")],
        key: Annotated[str, Field(description="字段名(如 loop/restore_charge)")],
        value: Annotated[str | int | bool, Field(description="字段值")],
        instance_idx: Annotated[int | None, Field(description="实例 idx(idx N→config/0N:idx 1→config/01 账号01;None=当前)")] = None,
        group_id: Annotated[str | None, Field(description="组 id;None=默认")] = None,
    ) -> dict:
        """写配置的简单字段(开关/下拉/输入)。操作类,改配置。

        只读字段(run_times/plan_id 等)拒绝。写穿 ctx 缓存实例。
        改配置前建议先调 ``describe_config`` 查字段结构、合法值与只读项。
        """
        ctx = backend.ctx
        entry = get_entry(app_id)
        if entry is None:
            return {'ok': False, 'error': f'不支持的 app_id: {app_id}'}
        if 'set' not in entry.supported_ops:
            return {'ok': False, 'error': f'{app_id} 不支持 set'}
        try:
            config = entry.get_config(ctx, instance_idx, group_id)
            if hasattr(config, '_RO_FIELDS') and key in config._RO_FIELDS:
                return {'ok': False, 'error': f'{key} 是只读字段(运行态/身份),不可 set'}
            if entry.field_schema and key not in entry.field_schema:
                return {'ok': False, 'error': f'{key} 不在 {app_id} 的可改字段中(可用: {list(entry.field_schema.keys())})'}
            if entry.field_schema and key in entry.field_schema:
                field_meta = entry.field_schema[key]
                if field_meta.get('type') == 'enum' and 'enum_cls' in field_meta:
                    valid_values = [m.value.value for m in field_meta['enum_cls']]
                    if value not in valid_values:
                        return {'ok': False, 'error': f'{key} 值 {value} 不合法(可用: {valid_values})'}
            config.update(key, value)
            config.save()
            return {'ok': True, 'app_id': app_id, 'key': key, 'value': value}
        except Exception as e:  # noqa: BLE001
            return {'ok': False, 'error': str(e)}
    return set_config


def make_describe_config(backend: ZzzBackendContext) -> Callable:
    """构造 ``describe_config`` tool(返回结构化 schema,智能体一看就懂)。"""
    async def describe_config(
        app_id: Annotated[str, Field(description="app 配置 id,如 charge_plan")],
        category: Annotated[str | None, Field(description="可选:查特定 category 的 mission_type 合法值")] = None,
        instance_idx: Annotated[int | None, Field(description="实例 idx(idx N→config/0N:idx 1→config/01 账号01;None=当前)")] = None,
        group_id: Annotated[str | None, Field(description="组 id;None=默认")] = None,
    ) -> dict:
        """描述配置结构(可改字段 / 只读 / list item 结构 / add 示例)。观察类。

        返回 set_fields(可改 + enum options) + ro_fields(只读) + list_fields(item 结构 + add_example)。
        智能体看到后可直接生成正确的 set/add 调用。不知道 app_id 时先 list_app_configs。
        """
        ctx = backend.ctx
        entry = get_entry(app_id)
        if entry is None:
            return {'ok': False, 'error': f'不支持的 app_id: {app_id}'}
        try:
            config = entry.get_config(ctx, instance_idx, group_id)
            ro_fields: set[str] = set(getattr(config, '_RO_FIELDS', set()))

            # set_fields
            set_fields = _build_set_fields(config, entry.field_schema, ro_fields)

            # list_fields
            ro_item = _ro_item_fields_for(app_id)
            list_fields = _build_list_fields(entry, ro_item)

            # category 参数:查 mission_type 合法值
            if category and list_fields:
                _inject_category_options(ctx, app_id, category, list_fields[0])

            return {
                'ok': True,
                'app_id': app_id,
                'description': entry.description,
                'set_fields': set_fields,
                'ro_fields': sorted(ro_fields),
                'list_fields': list_fields,
                'note': '所有 options 的 value 是 set/add 时要传的字符串(非 label);set_fields 与 ro_fields 互斥',
            }
        except Exception as e:  # noqa: BLE001
            return {'ok': False, 'error': str(e)}
    return describe_config


def _inject_category_options(
    ctx: Any, app_id: str, category: str, list_field: dict,
) -> None:
    """对 list_fields[0].item_fields 里 mission_type_name 注入 category 的合法值。"""
    if app_id == 'charge_plan':
        mission_types = [
            m.value for m in ctx.compendium_service.get_charge_plan_mission_type_list(category)
        ]
    elif app_id == 'notorious_hunt':
        mission_types = [
            m.value for m in ctx.compendium_service.get_notorious_hunt_plan_mission_type_list(category)
        ]
    else:
        return

    for f in list_field.get('item_fields', []):
        if f.get('name') == 'mission_type_name':
            f['options'] = mission_types
            f.pop('note', None)
            break


def make_list_app_configs(backend: ZzzBackendContext) -> Callable:
    """构造 ``list_app_configs`` tool(列出可改配置,首次发现入口)。"""
    async def list_app_configs(
        instance_idx: Annotated[int | None, Field(description="实例 idx(idx N→config/0N:idx 1→config/01 账号01;None=当前)")] = None,
    ) -> dict:
        """列出可改配置的 app_id(首次发现入口)。观察类。

        返回每个 config 的 app_id + description + supported_ops + item_kind + id_kind。
        智能体看到 item_kind 知道 item 是 dataclass / str / dict,不会套错模板。
        """
        configs: list[dict] = []
        for app_id, entry in all_entries().items():
            configs.append({
                'app_id': app_id,
                'description': entry.description,
                'supported_ops': list(entry.supported_ops),
                'item_kind': entry.item_kind,
                'id_kind': entry.id_kind,
            })
        return {'ok': True, 'configs': configs}
    return list_app_configs
