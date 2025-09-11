from __future__ import annotations

from typing import Any, Dict, List, Optional
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, validator

from zzz_od.api.deps import get_ctx
from zzz_od.api.models import GameAccountConfigDTO, OkResponse
from one_dragon.base.config.one_dragon_config import OneDragonInstance
from zzz_od.api.security import get_api_key_dependency


router = APIRouter(
    prefix="/api/v1/accounts",
    tags=["accounts"],
    dependencies=[Depends(get_api_key_dependency())],
)


# Pydantic models for better validation and documentation
class InstanceCreateRequest(BaseModel):
    name: Optional[str] = Field(None, description="实例显示名称")
    activate: bool = Field(False, description="是否创建后立即激活")
    clone_from: Optional[int] = Field(None, description="从哪个实例克隆配置")

class InstanceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, description="新实例名称")
    active_in_od: Optional[bool] = Field(None, description="是否参与一条龙批量运行")

class BatchOperationRequest(BaseModel):
    instance_ids: List[str] = Field(..., description="要操作的实例ID列表")
    operation: str = Field(..., description="操作类型: activate, deactivate, delete")

class InstanceStatus(BaseModel):
    id: str
    idx: int
    name: str
    active: bool
    active_in_od: bool
    last_active: Optional[datetime]
    health_status: str = "unknown"  # healthy, warning, error, unknown

class InstanceListResponse(BaseModel):
    active_id: str
    items: List[InstanceStatus]
    total_count: int

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


def _validate_instance_id(instance_id: str) -> int:
    """验证并解析实例ID"""
    try:
        if not instance_id.startswith("user-"):
            raise ValueError("实例ID格式错误，应为 user-{idx}")
        idx = int(instance_id.split("-")[-1])
        if idx < 0:
            raise ValueError("实例索引不能为负数")
        return idx
    except (ValueError, IndexError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"无效的实例ID: {instance_id}. {str(e)}"
        )


def _get_instance_or_404(instance_id: str, odc) -> OneDragonInstance:
    """获取实例或返回404错误"""
    idx = _validate_instance_id(instance_id)
    instance = next((i for i in odc.instance_list if i.idx == idx), None)
    if instance is None:
        raise HTTPException(
            status_code=404,
            detail=f"实例不存在: {instance_id}"
        )
    return instance


def _track_api_call(ctx, operation_name: str, properties: Dict[str, Any]) -> None:
    """记录多账户API调用埋点"""
    try:
        if hasattr(ctx, 'telemetry') and ctx.telemetry is not None:
            api_properties = {
                'operation_type': 'multi_account_api',
                'operation_name': operation_name,
                'total_instances': len(ctx.one_dragon_config.instance_list),
                'current_instance_idx': ctx.current_instance_idx,
                **properties
            }
            ctx.telemetry.capture_event('multi_account_api_call', api_properties)

            if 'duration_seconds' in properties:
                ctx.telemetry.track_performance_metric(
                    f'api_{operation_name}_duration',
                    properties['duration_seconds'],
                    {'success': properties.get('success', True)}
                )
    except Exception as e:
        from one_dragon.utils.log_utils import log
        log.debug(f'API埋点记录失败: {e}')


@router.get("/instances", response_model=InstanceListResponse)
def list_instances():
    """获取所有实例列表"""
    ctx = get_ctx()
    odc = ctx.one_dragon_config

    active = odc.current_active_instance.idx if odc.current_active_instance else (
        odc.instance_list[0].idx if odc.instance_list else 0
    )

    items = []
    for inst in odc.instance_list:
        # 简单的健康状态检查（可以扩展）
        health_status = "healthy"
        if not inst.active and not inst.active_in_od:
            health_status = "inactive"

        items.append(InstanceStatus(
            id=f"user-{inst.idx}",
            idx=inst.idx,
            name=inst.name,
            active=inst.active,
            active_in_od=inst.active_in_od,
            last_active=None,  # 可以从运行记录中获取
            health_status=health_status
        ))

    return InstanceListResponse(
        active_id=f"user-{active}",
        items=items,
        total_count=len(items)
    )


@router.get("/instances/{instance_id}", response_model=InstanceStatus)
def get_instance(instance_id: str):
    """获取单个实例详情"""
    ctx = get_ctx()
    odc = ctx.one_dragon_config
    instance = _get_instance_or_404(instance_id, odc)

    health_status = "healthy"
    if not instance.active and not instance.active_in_od:
        health_status = "inactive"

    return InstanceStatus(
        id=f"user-{instance.idx}",
        idx=instance.idx,
        name=instance.name,
        active=instance.active,
        active_in_od=instance.active_in_od,
        last_active=None,
        health_status=health_status
    )


@router.get("/whoami", response_model=Optional[InstanceStatus])
def whoami():
    """获取当前激活的实例"""
    ctx = get_ctx()
    odc = ctx.one_dragon_config
    curr = odc.current_active_instance

    if curr is None:
        return None

    health_status = "healthy"
    if not curr.active and not curr.active_in_od:
        health_status = "inactive"

    return InstanceStatus(
        id=f"user-{curr.idx}",
        idx=curr.idx,
        name=curr.name,
        active=curr.active,
        active_in_od=curr.active_in_od,
        last_active=None,
        health_status=health_status
    )


@router.put("/instances/{instance_id}/activate")
def activate_instance(instance_id: str) -> OkResponse:
    """激活指定的实例"""
    start_time = time.time()

    ctx = get_ctx()
    odc = ctx.one_dragon_config
    instance = _get_instance_or_404(instance_id, odc)

    previous_idx = ctx.current_instance_idx

    try:
        ctx.switch_instance(instance.idx)
        success = True
        error_message = None
    except Exception as e:
        success = False
        error_message = str(e)
        raise HTTPException(
            status_code=500,
            detail=f"激活实例失败: {error_message}"
        )
    finally:
        duration = time.time() - start_time
        _track_api_call(ctx, 'activate_instance', {
            'instance_id': instance_id,
            'target_idx': instance.idx,
            'previous_idx': previous_idx,
            'success': success,
            'error_message': error_message,
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/instances/{instance_id}/activate'
        })

    return OkResponse()


@router.post("/instances")
def create_instance(request: InstanceCreateRequest):
    """创建新实例"""
    start_time = time.time()

    ctx = get_ctx()
    odc = ctx.one_dragon_config
    previous_instance_count = len(odc.instance_list)

    try:
        # 如果指定了克隆源，则从源实例克隆配置
        if request.clone_from is not None:
            source_instance = next((i for i in odc.instance_list if i.idx == request.clone_from), None)
            if source_instance is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"源实例不存在: user-{request.clone_from}"
                )
            # 这里可以实现克隆逻辑
            new_inst = odc.create_new_instance(False)
        else:
            new_inst = odc.create_new_instance(False)

        # 设置名称
        final_name = request.name or f"实例 {new_inst.idx}"
        to_update = OneDragonInstance(
            idx=new_inst.idx,
            name=final_name,
            active=new_inst.active,
            active_in_od=new_inst.active_in_od,
        )
        odc.update_instance(to_update)

        # 激活（如果请求）
        activated = False
        if request.activate:
            odc.active_instance(new_inst.idx)
            ctx.switch_instance(new_inst.idx)
            activated = True

        # 获取更新后的实例
        refreshed = next((i for i in odc.instance_list if i.idx == new_inst.idx), new_inst)

        duration = time.time() - start_time
        _track_api_call(ctx, 'create_instance', {
            'new_instance_idx': new_inst.idx,
            'new_instance_name': refreshed.name,
            'clone_from': request.clone_from,
            'activated_immediately': activated,
            'previous_instance_count': previous_instance_count,
            'new_instance_count': len(odc.instance_list),
            'success': True,
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/instances'
        })

        return InstanceStatus(
            id=f"user-{refreshed.idx}",
            idx=refreshed.idx,
            name=refreshed.name,
            active=refreshed.active,
            active_in_od=refreshed.active_in_od,
            last_active=None,
            health_status="healthy"
        )

    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        _track_api_call(ctx, 'create_instance', {
            'clone_from': request.clone_from,
            'activate_requested': request.activate,
            'previous_instance_count': previous_instance_count,
            'success': False,
            'error_message': str(e),
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/instances'
        })
        raise HTTPException(
            status_code=500,
            detail=f"创建实例失败: {str(e)}"
        )


@router.put("/instances/{instance_id}")
def update_instance(instance_id: str, request: InstanceUpdateRequest) -> OkResponse:
    """更新实例信息"""
    start_time = time.time()

    ctx = get_ctx()
    odc = ctx.one_dragon_config
    existing = _get_instance_or_404(instance_id, odc)

    old_name = existing.name
    old_active_in_od = existing.active_in_od

    # 应用更新
    new_name = request.name if request.name is not None else existing.name
    new_active_in_od = request.active_in_od if request.active_in_od is not None else existing.active_in_od

    to_update = OneDragonInstance(
        idx=existing.idx,
        name=new_name,
        active=existing.active,
        active_in_od=new_active_in_od,
    )

    try:
        odc.update_instance(to_update)

        duration = time.time() - start_time
        _track_api_call(ctx, 'update_instance', {
            'instance_id': instance_id,
            'target_idx': existing.idx,
            'name_changed': old_name != new_name,
            'old_name': old_name,
            'new_name': new_name,
            'active_in_od_changed': old_active_in_od != new_active_in_od,
            'old_active_in_od': old_active_in_od,
            'new_active_in_od': new_active_in_od,
            'success': True,
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/instances/{instance_id}'
        })

        return OkResponse()

    except Exception as e:
        duration = time.time() - start_time
        _track_api_call(ctx, 'update_instance', {
            'instance_id': instance_id,
            'target_idx': existing.idx,
            'success': False,
            'error_message': str(e),
            'duration_seconds': round(duration, 3),
            'api_endpoint': '/instances/{instance_id}'
        })
        raise HTTPException(
            status_code=500,
            detail=f"更新实例失败: {str(e)}"
        )


@router.delete("/instances/{instance_id}")
def delete_instance(instance_id: str) -> OkResponse:
    """删除指定的实例"""
    ctx = get_ctx()
    odc = ctx.one_dragon_config

    if len(odc.instance_list) <= 1:
        raise HTTPException(
            status_code=400,
            detail="至少保留一个实例"
        )

    instance = _get_instance_or_404(instance_id, odc)

    deleting_active = instance.active
    odc.delete_instance(instance.idx)

    # 确保仍有激活实例
    if deleting_active:
        if odc.current_active_instance is None and odc.instance_list:
            new_idx = odc.instance_list[0].idx
            odc.active_instance(new_idx)
            ctx.switch_instance(new_idx)
        elif odc.current_active_instance is not None:
            ctx.switch_instance(odc.current_active_instance.idx)
    elif ctx.current_instance_idx == instance.idx:
        if odc.current_active_instance is not None:
            ctx.switch_instance(odc.current_active_instance.idx)

    return OkResponse()


@router.post("/instances/batch")
def batch_operation(request: BatchOperationRequest) -> Dict[str, Any]:
    """批量操作实例"""
    if not request.instance_ids:
        raise HTTPException(
            status_code=400,
            detail="实例ID列表不能为空"
        )

    ctx = get_ctx()
    odc = ctx.one_dragon_config

    results = []
    success_count = 0
    error_count = 0

    for instance_id in request.instance_ids:
        try:
            if request.operation == "activate":
                instance = _get_instance_or_404(instance_id, odc)
                ctx.switch_instance(instance.idx)
                results.append({"instance_id": instance_id, "success": True})
                success_count += 1

            elif request.operation == "deactivate":
                instance = _get_instance_or_404(instance_id, odc)
                # 停用实例的逻辑（如果有的话）
                results.append({"instance_id": instance_id, "success": True})
                success_count += 1

            elif request.operation == "delete":
                if len(odc.instance_list) <= 1:
                    results.append({
                        "instance_id": instance_id,
                        "success": False,
                        "error": "至少保留一个实例"
                    })
                    error_count += 1
                    continue

                instance = _get_instance_or_404(instance_id, odc)
                odc.delete_instance(instance.idx)
                results.append({"instance_id": instance_id, "success": True})
                success_count += 1

            else:
                results.append({
                    "instance_id": instance_id,
                    "success": False,
                    "error": f"不支持的操作: {request.operation}"
                })
                error_count += 1

        except Exception as e:
            results.append({
                "instance_id": instance_id,
                "success": False,
                "error": str(e)
            })
            error_count += 1

    return {
        "total_count": len(request.instance_ids),
        "success_count": success_count,
        "error_count": error_count,
        "results": results
    }


@router.post("/instances/{instance_id}/clone")
def clone_instance(instance_id: str, request: InstanceCreateRequest) -> InstanceStatus:
    """克隆指定的实例"""
    ctx = get_ctx()
    odc = ctx.one_dragon_config
    source_instance = _get_instance_or_404(instance_id, odc)

    try:
        # 创建新实例
        new_inst = odc.create_new_instance(False)

        # 复制源实例的配置
        clone_name = request.name or f"{source_instance.name} (副本)"
        to_update = OneDragonInstance(
            idx=new_inst.idx,
            name=clone_name,
            active=new_inst.active,
            active_in_od=source_instance.active_in_od,  # 复制源实例的设置
        )
        odc.update_instance(to_update)

        # 如果请求激活，则激活新实例
        if request.activate:
            odc.active_instance(new_inst.idx)
            ctx.switch_instance(new_inst.idx)

        # 获取更新后的实例
        refreshed = next((i for i in odc.instance_list if i.idx == new_inst.idx), new_inst)

        return InstanceStatus(
            id=f"user-{refreshed.idx}",
            idx=refreshed.idx,
            name=refreshed.name,
            active=refreshed.active,
            active_in_od=refreshed.active_in_od,
            last_active=None,
            health_status="healthy"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"克隆实例失败: {str(e)}"
        )


@router.get("/instances/stats")
def get_instances_stats() -> Dict[str, Any]:
    """获取实例统计信息"""
    ctx = get_ctx()
    odc = ctx.one_dragon_config

    total_instances = len(odc.instance_list)
    active_instances = sum(1 for i in odc.instance_list if i.active)
    active_in_od_instances = sum(1 for i in odc.instance_list if i.active_in_od)

    return {
        "total_instances": total_instances,
        "active_instances": active_instances,
        "inactive_instances": total_instances - active_instances,
        "active_in_od_instances": active_in_od_instances,
        "current_active_idx": ctx.current_instance_idx,
        "current_active_name": odc.current_active_instance.name if odc.current_active_instance else None
    }


@router.get("/instances/{instance_id}/config")
def export_instance_config(instance_id: str) -> Dict[str, Any]:
    """导出实例配置（用于备份或迁移）"""
    ctx = get_ctx()
    odc = ctx.one_dragon_config
    instance = _get_instance_or_404(instance_id, odc)

    # 这里可以导出实例相关的所有配置
    # 目前先导出基本信息，之后可以扩展
    return {
        "instance": {
            "idx": instance.idx,
            "name": instance.name,
            "active": instance.active,
            "active_in_od": instance.active_in_od
        },
        "exported_at": datetime.now().isoformat(),
        "version": "1.0"
    }


@router.post("/instances/{instance_id}/config/import")
def import_instance_config(instance_id: str, config: Dict[str, Any]) -> OkResponse:
    """导入实例配置"""
    ctx = get_ctx()
    odc = ctx.one_dragon_config
    instance = _get_instance_or_404(instance_id, odc)

    try:
        instance_config = config.get("instance", {})

        # 导入基本配置
        if "name" in instance_config:
            instance.name = instance_config["name"]
        if "active_in_od" in instance_config:
            instance.active_in_od = instance_config["active_in_od"]

        # 更新实例
        to_update = OneDragonInstance(
            idx=instance.idx,
            name=instance.name,
            active=instance.active,
            active_in_od=instance.active_in_od,
        )
        odc.update_instance(to_update)

        return OkResponse()

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"导入配置失败: {str(e)}"
        )


@router.get("/instances/health")
def get_instances_health() -> Dict[str, Any]:
    """获取所有实例的健康状态"""
    ctx = get_ctx()
    odc = ctx.one_dragon_config

    health_statuses = []
    for instance in odc.instance_list:
        # 简单的健康检查逻辑
        status = "healthy"
        issues = []

        if not instance.active and not instance.active_in_od:
            status = "inactive"
            issues.append("实例未激活")

        # 可以在这里添加更多健康检查逻辑
        # 比如检查配置文件是否存在、运行记录是否正常等

        health_statuses.append({
            "instance_id": f"user-{instance.idx}",
            "name": instance.name,
            "status": status,
            "issues": issues
        })

    overall_status = "healthy"
    if any(h["status"] != "healthy" for h in health_statuses):
        overall_status = "warning"
    if any(h["status"] == "error" for h in health_statuses):
        overall_status = "error"

    return {
        "overall_status": overall_status,
        "instances": health_statuses
    }


@router.get("/game-account", response_model=GameAccountConfigDTO)
def get_game_account(mask_sensitive: bool = Query(True, description="是否掩码敏感信息")):
    """获取游戏账户配置"""
    ctx = get_ctx()
    gac = ctx.game_account_config

    if mask_sensitive:
        # 掩码敏感信息
        masked_account = _mask_string(gac.account) if gac.account else None
        masked_password = _mask_string(gac.password) if gac.password else None
        masked_win_title = _mask_string(gac.custom_win_title) if gac.custom_win_title else None

        return GameAccountConfigDTO(
            platform=gac.platform,
            gameRegion=gac.game_region,
            gamePath=gac.game_path,
            gameLanguage=gac.game_language,
            useCustomWinTitle=gac.use_custom_win_title,
            customWinTitle=masked_win_title,
            account=masked_account,
            password=masked_password,
        )
    else:
        # 返回完整信息（需要特殊权限）
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


def _mask_string(value: str, visible_chars: int = 2) -> str:
    """掩码字符串，只显示前几个字符"""
    if not value or len(value) <= visible_chars:
        return "*" * len(value) if value else ""

    return value[:visible_chars] + "*" * (len(value) - visible_chars)


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
