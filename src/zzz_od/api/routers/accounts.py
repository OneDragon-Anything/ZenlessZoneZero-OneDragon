from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from zzz_od.api.deps import get_ctx
from zzz_od.api.models import GameAccountConfigDTO, OkResponse
from one_dragon.base.config.one_dragon_config import OneDragonInstance
from zzz_od.api.security import get_api_key_dependency


router = APIRouter(
    prefix="/api/v1/accounts",
    tags=["accounts"],
    dependencies=[Depends(get_api_key_dependency())],
)


def _track_api_call(ctx, operation_name: str, properties: Dict[str, Any]) -> None:
    """
    记录多账户API调用埋点
    :param ctx: ZContext实例
    :param operation_name: 操作名称
    :param properties: 事件属性
    :return:
    """
    try:
        if hasattr(ctx, 'telemetry') and ctx.telemetry is not None:
            # 添加通用API属性
            api_properties = {
                'operation_type': 'multi_account_api',
                'operation_name': operation_name,
                'total_instances': len(ctx.one_dragon_config.instance_list),
                'current_instance_idx': ctx.current_instance_idx,
                **properties
            }

            # 记录API调用事件
            ctx.telemetry.capture_event('multi_account_api_call', api_properties)

            # 如果有性能数据，记录性能指标
            if 'duration_seconds' in properties:
                ctx.telemetry.track_performance_metric(
                    f'api_{operation_name}_duration',
                    properties['duration_seconds'],
                    {'success': properties.get('success', True)}
                )
    except Exception as e:
        # 埋点失败不应该影响API功能
        from one_dragon.utils.log_utils import log
        log.debug(f'API埋点记录失败: {e}')


@router.get("/instances")
def list_instances():
    ctx = get_ctx()
    odc = ctx.one_dragon_config
    active = odc.current_active_instance.idx if odc.current_active_instance else (odc.instance_list[0].idx if odc.instance_list else 0)
    items: List[Dict[str, Any]] = [
        {
            "id": f"user-{inst.idx}",
            "name": inst.name,
            "idx": inst.idx,
            "active": inst.active,
            "activeInOD": inst.active_in_od,
        }
        for inst in odc.instance_list
    ]
    return {"activeId": f"user-{active}", "items": items}


@router.get("/whoami")
def whoami():
    ctx = get_ctx()
    odc = ctx.one_dragon_config
    curr = odc.current_active_instance
    return None if curr is None else {"id": f"user-{curr.idx}", "idx": curr.idx, "name": curr.name}


@router.post("/instances/{instance_id}:activate")
def activate_instance(instance_id: str) -> OkResponse:
    # instance_id like user-1
    import time
    start_time = time.time()

    try:
        idx = int(instance_id.split("-")[-1])
    except Exception:
        idx = 0

    ctx = get_ctx()
    previous_idx = ctx.current_instance_idx

    try:
        ctx.switch_instance(idx)
        success = True
        error_message = None
    except Exception as e:
        success = False
        error_message = str(e)
        raise
    finally:
        # 记录API调用埋点
        duration = time.time() - start_time
        _track_api_call(ctx, 'activate_instance', {
            'instance_id': instance_id,
            'target_idx': idx,
            'previous_idx': previous_idx,
            'success': success,
            'error_message': error_message,
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/instances/{instance_id}:activate'
        })

    return OkResponse()


@router.post("/instances")
def create_instance(payload: Dict[str, Any] | None = None):
    """创建新实例。
    payload 可包含：
    - name: 可选，实例显示名称
    - activate: 可选，是否创建后立即设为当前激活实例
    """
    import time
    start_time = time.time()

    payload = payload or {}
    name = payload.get("name")
    activate = bool(payload.get("activate", False))

    ctx = get_ctx()
    odc = ctx.one_dragon_config
    previous_instance_count = len(odc.instance_list)

    try:
        new_inst = odc.create_new_instance(False)

        # 重命名（可选）
        renamed = False
        if isinstance(name, str) and name.strip():
            to_update = OneDragonInstance(
                idx=new_inst.idx,
                name=name.strip(),
                active=new_inst.active,
                active_in_od=new_inst.active_in_od,
            )
            odc.update_instance(to_update)
            renamed = True

        # 激活（可选）
        activated = False
        if activate:
            odc.active_instance(new_inst.idx)
            ctx.switch_instance(new_inst.idx)
            activated = True

        # 返回最新快照
        refreshed = next((i for i in odc.instance_list if i.idx == new_inst.idx), new_inst)

        # 记录创建实例埋点
        duration = time.time() - start_time
        _track_api_call(ctx, 'create_instance', {
            'new_instance_idx': new_inst.idx,
            'new_instance_name': refreshed.name,
            'custom_name_provided': bool(name and name.strip()),
            'renamed': renamed,
            'activated_immediately': activated,
            'previous_instance_count': previous_instance_count,
            'new_instance_count': len(odc.instance_list),
            'success': True,
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/instances'
        })

        return {
            "id": f"user-{refreshed.idx}",
            "idx": refreshed.idx,
            "name": refreshed.name,
            "active": refreshed.active,
            "activeInOD": refreshed.active_in_od,
        }
    except Exception as e:
        # 记录失败的创建实例埋点
        duration = time.time() - start_time
        _track_api_call(ctx, 'create_instance', {
            'custom_name_provided':bool(name and name.strip()),
            'activate_requested': activate,
            'previous_instance_count': previous_instance_count,
            'success': False,
            'error_message': str(e),
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/instances'
        })
        raise


@router.put("/instances/{instance_id}")
def update_instance(instance_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新实例：支持改名与 activeInOD 切换。
    - name: 可选，新名称
    - activeInOD: 可选，是否参与一条龙批量运行
    """
    import time
    start_time = time.time()

    try:
        idx = int(instance_id.split("-")[-1])
    except Exception:
        idx = 0

    ctx = get_ctx()
    odc = ctx.one_dragon_config
    existing = next((i for i in odc.instance_list if i.idx == idx), None)

    if existing is None:
        # 记录实例未找到的埋点
        duration = time.time() - start_time
        _track_api_call(ctx, 'update_instance', {
            'instance_id': instance_id,
            'target_idx': idx,
            'success': False,
            'error_code': 'INSTANCE_NOT_FOUND',
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/instances/{instance_id}'
        })
        return {"ok": False, "error": {"code": "INSTANCE_NOT_FOUND", "message": instance_id}}

    # 记录变更前的状态
    old_name = existing.name
    old_active_in_od = existing.active_in_od

    name = payload.get("name", existing.name)
    active_in_od = payload.get("activeInOD", existing.active_in_od)

    to_update = OneDragonInstance(
        idx=existing.idx,
        name=name,
        active=existing.active,
        active_in_od=bool(active_in_od),
    )

    try:
        odc.update_instance(to_update)

        # 记录成功的更新埋点
        duration = time.time() - start_time
        _track_api_call(ctx, 'update_instance', {
            'instance_id': instance_id,
            'target_idx': idx,
            'name_changed': old_name != name,
            'old_name': old_name,
            'new_name': name,
            'active_in_od_changed': old_active_in_od != bool(active_in_od),
            'old_active_in_od': old_active_in_od,
            'new_active_in_od': bool(active_in_od),
            'success': True,
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/instances/{instance_id}'
        })

        return {"ok": True}
    except Exception as e:
        # 记录失败的更新埋点
        duration = time.time() - start_time
        _track_api_call(ctx, 'update_instance', {
            'instance_id': instance_id,
            'target_idx': idx,
            'success': False,
            'error_message': str(e),
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/instances/{instance_id}'
        })
        raise


@router.delete("/instances/{instance_id}")
def delete_instance(instance_id: str) -> Dict[str, Any]:
    try:
        idx = int(instance_id.split("-")[-1])
    except Exception:
        idx = 0
    ctx = get_ctx()
    odc = ctx.one_dragon_config

    if len(odc.instance_list) <= 1:
        return {"ok": False, "error": {"code": "ONLY_ONE_INSTANCE", "message": "至少保留一个实例"}}

    deleting_active = any(i.idx == idx and i.active for i in odc.instance_list)
    odc.delete_instance(idx)

    # 确保仍有激活实例，并同步到 ctx
    if deleting_active:
        if odc.current_active_instance is None and odc.instance_list:
            new_idx = odc.instance_list[0].idx
            odc.active_instance(new_idx)
            ctx.switch_instance(new_idx)
        elif odc.current_active_instance is not None:
            ctx.switch_instance(odc.current_active_instance.idx)
    elif ctx.current_instance_idx == idx:
        # 删除的不是 active，但 ctx 指针指向该实例（理论不该发生），做兜底
        if odc.current_active_instance is not None:
            ctx.switch_instance(odc.current_active_instance.idx)

    return {"ok": True}


@router.get("/game-account", response_model=GameAccountConfigDTO)
def get_game_account() -> GameAccountConfigDTO:
    ctx = get_ctx()
    gac = ctx.game_account_config
    return GameAccountConfigDTO(
        platform=gac.platform,
        gameRegion=gac.game_region,
        gamePath=gac.game_path,
        gameLanguage=gac.game_language,
        useCustomWinTitle=gac.use_custom_win_title,
        customWinTitle=gac.custom_win_title,
        account=gac.account,
        password=gac.password,
    )


@router.put("/game-account")
def update_game_account(payload: Dict[str, Any]) -> OkResponse:
    import time
    start_time = time.time()

    ctx = get_ctx()
    gac = ctx.game_account_config

    # 记录变更前的状态（不记录敏感信息）
    changes_made = []

    try:
        if "platform" in payload:
            old_value = gac.platform
            gac.platform = payload["platform"]
            changes_made.append({"field": "platform", "changed": old_value != payload["platform"]})

        if "gameRegion" in payload:
            old_value = gac.game_region
            gac.game_region = payload["gameRegion"]
            changes_made.append({"field": "gameRegion", "changed": old_value != payload["gameRegion"]})

        if "gamePath" in payload:
            old_value = gac.game_path
            gac.game_path = payload["gamePath"]
            changes_made.append({"field": "gamePath", "changed": old_value != payload["gamePath"]})

        if "gameLanguage" in payload:
            old_value = gac.game_language
            gac.game_language = payload["gameLanguage"]
            changes_made.append({"field": "gameLanguage", "changed": old_value != payload["gameLanguage"]})

        if "useCustomWinTitle" in payload:
            old_value = gac.use_custom_win_title
            gac.use_custom_win_title = bool(payload["useCustomWinTitle"])
            changes_made.append({"field": "useCustomWinTitle", "changed": old_value != bool(payload["useCustomWinTitle"])})

        if "customWinTitle" in payload:
            old_value = gac.custom_win_title
            gac.custom_win_title = payload["customWinTitle"]
            changes_made.append({"field": "customWinTitle", "changed": old_value != payload["customWinTitle"]})

        if "account" in payload:
            # 不记录账号的具体值，只记录是否变更
            old_value = gac.account
            gac.account = payload["account"]
            changes_made.append({"field": "account", "changed": old_value != payload["account"]})

        if "password" in payload:
            # 不记录密码的具体值，只记录是否变更
            old_value = gac.password
            gac.password = payload["password"]
            changes_made.append({"field": "password", "changed": old_value != payload["password"]})

        # 记录游戏账户配置更新埋点
        duration = time.time() - start_time
        _track_api_call(ctx, 'update_game_account', {
            'fields_updated': [change["field"] for change in changes_made],
            'changes_made': [change for change in changes_made if change["changed"]],
            'total_fields_changed': sum(1 for change in changes_made if change["changed"]),
            'instance_idx': ctx.current_instance_idx,
            'success': True,
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/game-account'
        })

        return OkResponse()
    except Exception as e:
        # 记录失败的配置更新埋点
        duration = time.time() - start_time
        _track_api_call(ctx, 'update_game_account', {
            'fields_attempted': list(payload.keys()),
            'instance_idx': ctx.current_instance_idx,
            'success': False,
            'error_message': str(e),
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/game-account'
        })
        raise


@router.get("/options")
def get_account_options() -> Dict[str, Any]:
    """读取多账户相关全局选项。"""
    ctx = get_ctx()
    odc = ctx.one_dragon_config
    return {
        "instanceRun": odc.instance_run,
        "afterDone": odc.after_done,
    }


@router.put("/options")
def update_account_options(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新多账户相关全局选项。
    - instanceRun: ALL | CURRENT
    - afterDone: NONE | CLOSE_GAME | SHUTDOWN
    """
    ctx = get_ctx()
    odc = ctx.one_dragon_config
    if "instanceRun" in payload:
        odc.instance_run = payload["instanceRun"]
    if "afterDone" in payload:
        odc.after_done = payload["afterDone"]
    return {"ok": True}
