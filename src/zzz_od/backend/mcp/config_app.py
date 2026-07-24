"""MCP 配置修改工具:通用入口 + app_id 路由到领域方法(写穿 ctx + 校验前置)。

详见 `docs/superpowers/specs/2026-07-24-mcp-config-design.md`(v5)。
v1 最小闭环:add_config_item(charge_plan plan_list)。
"""
from collections.abc import Callable
from typing import Annotated

from pydantic import Field

from zzz_od.backend.backend_context import ZzzBackendContext
from zzz_od.backend.config_router import get_entry


def make_add_config_item(backend: ZzzBackendContext) -> Callable:
    """构造 ``add_config_item`` tool(模块级,便于独立测试)。"""
    async def add_config_item(
        app_id: Annotated[str, Field(description="app 配置 id,如 charge_plan")],
        list_field: Annotated[str, Field(description="列表字段名(如 plan_list);v1 仅 plan_list")],
        item_dict: Annotated[dict, Field(description="列表项 dict(经 from_dict 反序列化)")],
        instance_idx: Annotated[int | None, Field(description="实例 idx;None=当前实例")] = None,
        group_id: Annotated[str | None, Field(description="组 id;None=默认组")] = None,
    ) -> dict:
        """加一个数据类列表项(如 charge_plan plan)。操作类,改配置。

        通用入口,按 ``app_id`` 路由到该 config 的领域方法(如 ``add_plan``)。
        **写入前校验**(结构 + 业务),不合法拒绝;**写穿 ctx 缓存实例**(天然一致)。
        详见 spec v5。

        Returns:
            ``{ok, app_id, list_field, error?}``;不支持的 app_id / 校验失败 / 异常 → ok=False。
        """
        ctx = backend.ctx
        entry = get_entry(app_id)
        if entry is None:
            return {'ok': False, 'error': f'不支持的 app_id: {app_id}'}
        try:
            config = entry.get_config(ctx, instance_idx, group_id)
            item = entry.item_from_dict(item_dict)
            err = entry.validate_item(ctx, item)
            if err:
                return {'ok': False, 'error': err}
            entry.add(config, item)
            # 返回新 item 的 id(charge_plan/notorious_hunt 按 plan_id 寻址,方便 update/delete)
            new_id = None
            if hasattr(config, 'plan_list') and config.plan_list:
                new_id = config.plan_list[-1].plan_id
            return {'ok': True, 'app_id': app_id, 'list_field': list_field, 'id': new_id}
        except Exception as e:  # noqa: BLE001 工具层兜底
            return {'ok': False, 'error': str(e)}
    return add_config_item


def make_delete_config_item(backend: ZzzBackendContext) -> Callable:
    """构造 ``delete_config_item`` tool(模块级,便于独立测试)。"""
    async def delete_config_item(
        app_id: Annotated[str, Field(description="app 配置 id,如 charge_plan")],
        list_field: Annotated[str, Field(description="列表字段名(如 plan_list);v1 仅 plan_list")],
        id: Annotated[str, Field(description="项标识:charge_plan/notorious_hunt 用 plan_id;team/shiyu 用 idx;standalone_app/_group 用 app_id")],
        instance_idx: Annotated[int | None, Field(description="实例 idx;None=当前实例")] = None,
        group_id: Annotated[str | None, Field(description="组 id;None=默认组")] = None,
    ) -> dict:
        """删一个数据类列表项(如 charge_plan plan)。操作类,改配置,可逆性低。

        通用入口,按 ``app_id`` 路由到该 config 的领域方法(如 ``delete_plan``)。
        ``id`` 按寻址键(plan_id/idx/app_id)解析。写穿 ctx 缓存实例。
        **禁止删除 one_dragon instance**(delete_instance 会 rmtree 整个实例目录)。

        Returns:
            ``{ok, app_id, list_field, id, error?}``;不支持的 app_id / 未找到 id / 异常 → ok=False。
        """
        ctx = backend.ctx
        entry = get_entry(app_id)
        if entry is None:
            return {'ok': False, 'error': f'不支持的 app_id: {app_id}'}
        try:
            config = entry.get_config(ctx, instance_idx, group_id)
            deleted = entry.delete(config, id)
            if not deleted:
                return {'ok': False, 'error': f'未找到 id={id}'}
            return {'ok': True, 'app_id': app_id, 'list_field': list_field, 'id': id}
        except Exception as e:  # noqa: BLE001 工具层兜底
            return {'ok': False, 'error': str(e)}
    return delete_config_item


def make_get_config(backend: ZzzBackendContext) -> Callable:
    """构造 ``get_config`` tool(读配置字段/全 data)。"""
    async def get_config(
        app_id: Annotated[str, Field(description="app 配置 id,如 charge_plan")],
        key: Annotated[str | None, Field(description="字段名;None=返全 data")] = None,
        instance_idx: Annotated[int | None, Field(description="实例 idx;None=当前")] = None,
        group_id: Annotated[str | None, Field(description="组 id;None=默认")] = None,
    ) -> dict:
        """读配置字段或全部 data。观察类,不改配置。

        Returns:
            ``{ok, app_id, key?, value?/data, error?}``。
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
        key: Annotated[str, Field(description="字段名(如 loop/skip_plan/restore_charge)")],
        value: Annotated[str | int | bool, Field(description="字段值")],
        instance_idx: Annotated[int | None, Field(description="实例 idx;None=当前")] = None,
        group_id: Annotated[str | None, Field(description="组 id;None=默认")] = None,
    ) -> dict:
        """写配置的简单字段(开关/下拉/输入)。操作类,改配置。

        只读字段(run_times/plan_id 等)拒绝。写穿 ctx 缓存实例。

        Returns:
            ``{ok, app_id, key, value, error?}``。
        """
        ctx = backend.ctx
        entry = get_entry(app_id)
        if entry is None:
            return {'ok': False, 'error': f'不支持的 app_id: {app_id}'}
        try:
            config = entry.get_config(ctx, instance_idx, group_id)
            if hasattr(config, '_RO_FIELDS') and key in config._RO_FIELDS:
                return {'ok': False, 'error': f'{key} 是只读字段(运行态/身份),不可 set'}
            config.update(key, value)
            config.save()
            return {'ok': True, 'app_id': app_id, 'key': key, 'value': value}
        except Exception as e:  # noqa: BLE001
            return {'ok': False, 'error': str(e)}
    return set_config
