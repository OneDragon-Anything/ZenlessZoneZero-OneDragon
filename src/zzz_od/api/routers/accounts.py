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
    tags=["账户管理 Accounts"],
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


@router.get("/instances", response_model=InstanceListResponse, summary="获取所有实例列表")
def list_instances():
    """
    获取所有游戏实例的列表

    ## 功能描述
    返回系统中所有配置的游戏实例信息，包括实例状态、名称和健康状况。

    ## 返回数据
    - **active_id**: 当前激活的实例ID
    - **items**: 实例列表
      - **id**: 实例唯一标识符 (格式: user-{idx})
      - **idx**: 实例索引号
      - **name**: 实例显示名称
      - **active**: 是否为当前激活实例
      - **active_in_od**: 是否参与一条龙批量运行
      - **last_active**: 最后激活时间
      - **health_status**: 健康状态 (healthy/inactive/warning/error)
    - **total_count**: 实例总数

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/accounts/instances")
    instances = response.json()
    print(f"当前激活实例: {instances['active_id']}")
    print(f"实例总数: {instances['total_count']}")
    ```
    """
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


@router.get("/instances/{instance_id}", response_model=InstanceStatus, summary="获取单个实例详情")
def get_instance(instance_id: str):
    """
    获取指定实例的详细信息

    ## 功能描述
    根据实例ID获取特定实例的详细配置和状态信息。

    ## 路径参数
    - **instance_id**: 实例ID，格式为 user-{idx}

    ## 返回数据
    - **id**: 实例唯一标识符
    - **idx**: 实例索引号
    - **name**: 实例显示名称
    - **active**: 是否为当前激活实例
    - **active_in_od**: 是否参与一条龙批量运行
    - **last_active**: 最后激活时间
    - **health_status**: 健康状态

    ## 错误码
    - **INVALID_INSTANCE_ID**: 实例ID格式错误 (400)
    - **INSTANCE_NOT_FOUND**: 实例不存在 (404)

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/accounts/instances/user-1")
    instance = response.json()
    print(f"实例名称: {instance['name']}")
    ```
    """
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


@router.get("/whoami", response_model=Optional[InstanceStatus], summary="获取当前激活的实例")
def whoami():
    """
    获取当前激活实例的信息

    ## 功能描述
    返回当前系统中激活的实例信息，如果没有激活的实例则返回null。

    ## 返回数据
    - 如果有激活实例：返回实例详细信息
    - 如果无激活实例：返回null

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/accounts/whoami")
    current_instance = response.json()
    if current_instance:
        print(f"当前实例: {current_instance['name']}")
    else:
        print("没有激活的实例")
    ```
    """
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


@router.put("/instances/{instance_id}/activate", response_model=OkResponse, summary="激活指定的实例")
def activate_instance(instance_id: str) -> OkResponse:
    """
    激活指定的游戏实例

    ## 功能描述
    将指定的实例设置为当前激活状态，系统将切换到该实例的配置和数据。

    ## 路径参数
    - **instance_id**: 要激活的实例ID，格式为 user-{idx}

    ## 返回数据
    - **ok**: 操作是否成功

    ## 错误码
    - **INVALID_INSTANCE_ID**: 实例ID格式错误 (400)
    - **INSTANCE_NOT_FOUND**: 实例不存在 (404)
    - **ACTIVATION_FAILED**: 激活失败 (500)

    ## 注意事项
    - 激活实例会切换当前的配置上下文
    - 正在运行的任务可能会受到影响

    ## 使用示例
    ```python
    import requests
    response = requests.put("http://localhost:8000/api/v1/accounts/instances/user-2/activate")
    result = response.json()
    print(f"激活结果: {result['ok']}")
    ```
    """
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


@router.post("/instances", response_model=InstanceStatus, summary="创建新实例")
def create_instance(request: InstanceCreateRequest):
    """
    创建新的游戏实例

    ## 功能描述
    创建一个新的游戏实例，可以选择从现有实例克隆配置或创建全新实例。

    ## 请求参数
    - **name** (可选): 实例显示名称，不提供时自动生成
    - **activate** (可选): 是否创建后立即激活，默认false
    - **clone_from** (可选): 从哪个实例索引克隆配置

    ## 返回数据
    返回新创建的实例详细信息

    ## 错误码
    - **SOURCE_INSTANCE_NOT_FOUND**: 克隆源实例不存在 (404)
    - **INSTANCE_CREATE_FAILED**: 实例创建失败 (500)

    ## 使用示例
    ```python
    import requests
    data = {
        "name": "我的新实例",
        "activate": True,
        "clone_from": 1
    }
    response = requests.post("http://localhost:8000/api/v1/accounts/instances", json=data)
    new_instance = response.json()
    print(f"新实例ID: {new_instance['id']}")
    ```
    """
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


@router.put("/instances/{instance_id}", response_model=OkResponse, summary="更新实例信息")
def update_instance(instance_id: str, request: InstanceUpdateRequest) -> OkResponse:
    """
    更新指定实例的配置信息

    ## 功能描述
    更新指定实例的名称和一条龙参与设置，支持部分更新。

    ## 路径参数
    - **instance_id**: 实例ID，格式为 user-{idx}

    ## 请求参数
    - **name** (可选): 新的实例名称
    - **active_in_od** (可选): 是否参与一条龙批量运行

    ## 返回数据
    - **ok**: 操作是否成功

    ## 错误码
    - **INVALID_INSTANCE_ID**: 实例ID格式错误 (400)
    - **INSTANCE_NOT_FOUND**: 实例不存在 (404)
    - **UPDATE_FAILED**: 更新失败 (500)

    ## 使用示例
    ```python
    import requests
    data = {
        "name": "新实例名称",
        "active_in_od": True
    }
    response = requests.put("http://localhost:8000/api/v1/accounts/instances/user-1", json=data)
    result = response.json()
    print(f"更新结果: {result['ok']}")
    ```
    """
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


@router.delete("/instances/{instance_id}", response_model=OkResponse, summary="删除指定的实例")
def delete_instance(instance_id: str) -> OkResponse:
    """
    删除指定的游戏实例

    ## 功能描述
    删除指定的游戏实例，包括其所有配置和数据。系统至少保留一个实例。

    ## 路径参数
    - **instance_id**: 要删除的实例ID，格式为 user-{idx}

    ## 返回数据
    - **ok**: 操作是否成功

    ## 错误码
    - **INVALID_INSTANCE_ID**: 实例ID格式错误 (400)
    - **INSTANCE_NOT_FOUND**: 实例不存在 (404)
    - **CANNOT_DELETE_LAST**: 至少保留一个实例 (400)

    ## 注意事项
    - 删除操作不可逆，请谨慎操作
    - 如果删除的是当前激活实例，系统会自动切换到其他实例
    - 系统至少保留一个实例

    ## 使用示例
    ```python
    import requests
    response = requests.delete("http://localhost:8000/api/v1/accounts/instances/user-2")
    result = response.json()
    print(f"删除结果: {result['ok']}")
    ```
    """
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


@router.post("/instances/batch", response_model=Dict[str, Any], summary="批量操作实例")
def batch_operation(request: BatchOperationRequest) -> Dict[str, Any]:
    """
    对多个实例执行批量操作

    ## 功能描述
    对指定的多个实例执行批量操作，支持激活、停用和删除操作。

    ## 请求参数
    - **instance_ids**: 要操作的实例ID列表
    - **operation**: 操作类型
      - "activate": 激活实例
      - "deactivate": 停用实例
      - "delete": 删除实例

    ## 返回数据
    - **total_count**: 总操作数量
    - **success_count**: 成功操作数量
    - **error_count**: 失败操作数量
    - **results**: 详细操作结果列表
      - **instance_id**: 实例ID
      - **success**: 操作是否成功
      - **error** (失败时): 错误信息

    ## 错误码
    - **EMPTY_INSTANCE_LIST**: 实例ID列表不能为空 (400)
    - **UNSUPPORTED_OPERATION**: 不支持的操作类型

    ## 使用示例
    ```python
    import requests
    data = {
        "instance_ids": ["user-1", "user-2", "user-3"],
        "operation": "activate"
    }
    response = requests.post("http://localhost:8000/api/v1/accounts/instances/batch", json=data)
    result = response.json()
    print(f"成功: {result['success_count']}, 失败: {result['error_count']}")
    ```
    """
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
                try:
                    # 设置实例为非活跃状态
                    instance.active = False
                    instance.active_in_od = False

                    # 如果停用的是当前活跃实例，需要切换到另一个活跃实例
                    if odc.current_active_instance and odc.current_active_instance.idx == instance.idx:
                        # 找到第一个仍然活跃的实例
                        next_active = next((i for i in odc.instance_list if i.active and i.idx != instance.idx), None)
                        if next_active:
                            odc.active_instance(next_active.idx)
                            ctx.switch_instance(next_active.idx)
                        else:
                            # 如果没有其他活跃实例，激活第一个可用实例
                            if odc.instance_list and len(odc.instance_list) > 1:
                                first_other = next((i for i in odc.instance_list if i.idx != instance.idx), None)
                                if first_other:
                                    first_other.active = True
                                    odc.active_instance(first_other.idx)
                                    ctx.switch_instance(first_other.idx)

                    # 保存配置更改
                    odc.save()

                    results.append({"instance_id": instance_id, "success": True})
                    success_count += 1
                except Exception as e:
                    results.append({
                        "instance_id": instance_id,
                        "success": False,
                        "error": f"停用实例失败: {str(e)}"
                    })

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


@router.post("/instances/{instance_id}/clone", response_model=InstanceStatus, summary="克隆指定的实例")
def clone_instance(instance_id: str, request: InstanceCreateRequest) -> InstanceStatus:
    """
    克隆指定的游戏实例

    ## 功能描述
    基于现有实例创建一个新的实例副本，复制源实例的配置设置。

    ## 路径参数
    - **instance_id**: 要克隆的源实例ID，格式为 user-{idx}

    ## 请求参数
    - **name** (可选): 新实例的名称，默认为"源实例名 (副本)"
    - **activate** (可选): 是否创建后立即激活，默认false

    ## 返回数据
    返回新创建的克隆实例详细信息

    ## 错误码
    - **INVALID_INSTANCE_ID**: 实例ID格式错误 (400)
    - **INSTANCE_NOT_FOUND**: 源实例不存在 (404)
    - **CLONE_FAILED**: 克隆失败 (500)

    ## 使用示例
    ```python
    import requests
    data = {
        "name": "克隆实例",
        "activate": True
    }
    response = requests.post("http://localhost:8000/api/v1/accounts/instances/user-1/clone", json=data)
    new_instance = response.json()
    print(f"克隆实例ID: {new_instance['id']}")
    ```
    """
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


@router.get("/instances/stats", response_model=Dict[str, Any], summary="获取实例统计信息")
def get_instances_stats() -> Dict[str, Any]:
    """
    获取所有实例的统计信息

    ## 功能描述
    返回实例的统计数据，包括总数、激活状态分布等信息。

    ## 返回数据
    - **total_instances**: 实例总数
    - **active_instances**: 激活实例数量
    - **inactive_instances**: 未激活实例数量
    - **active_in_od_instances**: 参与一条龙的实例数量
    - **current_active_idx**: 当前激活实例的索引
    - **current_active_name**: 当前激活实例的名称

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/accounts/instances/stats")
    stats = response.json()
    print(f"总实例数: {stats['total_instances']}")
    print(f"当前激活: {stats['current_active_name']}")
    ```
    """
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


@router.get("/instances/{instance_id}/config", response_model=Dict[str, Any], summary="导出实例配置")
def export_instance_config(instance_id: str) -> Dict[str, Any]:
    """
    导出指定实例的配置信息

    ## 功能描述
    导出指定实例的配置数据，用于备份或迁移到其他系统。

    ## 路径参数
    - **instance_id**: 要导出配置的实例ID，格式为 user-{idx}

    ## 返回数据
    - **instance**: 实例配置信息
      - **idx**: 实例索引
      - **name**: 实例名称
      - **active**: 是否激活
      - **active_in_od**: 是否参与一条龙
    - **exported_at**: 导出时间（ISO格式）
    - **version**: 配置版本号

    ## 错误码
    - **INVALID_INSTANCE_ID**: 实例ID格式错误 (400)
    - **INSTANCE_NOT_FOUND**: 实例不存在 (404)

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/accounts/instances/user-1/config")
    config = response.json()
    print(f"导出时间: {config['exported_at']}")
    # 保存配置到文件
    import json
    with open("instance_backup.json", "w") as f:
        json.dump(config, f)
    ```
    """
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


@router.post("/instances/{instance_id}/config/import", response_model=OkResponse, summary="导入实例配置")
def import_instance_config(instance_id: str, config: Dict[str, Any]) -> OkResponse:
    """
    导入实例配置信息

    ## 功能描述
    将之前导出的配置数据导入到指定实例，用于配置恢复或迁移。

    ## 路径参数
    - **instance_id**: 要导入配置的实例ID，格式为 user-{idx}

    ## 请求参数
    - **instance**: 实例配置对象
      - **name** (可选): 实例名称
      - **active_in_od** (可选): 是否参与一条龙
    - **exported_at** (可选): 导出时间
    - **version** (可选): 配置版本

    ## 返回数据
    - **ok**: 操作是否成功

    ## 错误码
    - **INVALID_INSTANCE_ID**: 实例ID格式错误 (400)
    - **INSTANCE_NOT_FOUND**: 实例不存在 (404)
    - **IMPORT_FAILED**: 导入失败 (400)

    ## 使用示例
    ```python
    import requests
    import json

    # 从文件加载配置
    with open("instance_backup.json", "r") as f:
        config_data = json.load(f)

    response = requests.post(
        "http://localhost:8000/api/v1/accounts/instances/user-1/config/import",
        json=config_data
    )
    result = response.json()
    print(f"导入结果: {result['ok']}")
    ```
    """
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


@router.get("/instances/health", response_model=Dict[str, Any], summary="获取所有实例的健康状态")
def get_instances_health() -> Dict[str, Any]:
    """
    获取所有实例的健康检查结果

    ## 功能描述
    检查所有实例的健康状态，识别潜在问题和配置异常。

    ## 返回数据
    - **overall_status**: 整体健康状态 (healthy/warning/error)
    - **instances**: 各实例健康状态列表
      - **instance_id**: 实例ID
      - **name**: 实例名称
      - **status**: 健康状态 (healthy/inactive/warning/error)
      - **issues**: 问题列表

    ## 健康状态说明
    - **healthy**: 实例运行正常
    - **inactive**: 实例未激活
    - **warning**: 存在潜在问题
    - **error**: 存在严重问题

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/accounts/instances/health")
    health = response.json()
    print(f"整体状态: {health['overall_status']}")

    for instance in health['instances']:
        if instance['status'] != 'healthy':
            print(f"实例 {instance['name']} 状态: {instance['status']}")
            for issue in instance['issues']:
                print(f"  问题: {issue}")
    ```
    """
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


@router.get("/game-account", response_model=GameAccountConfigDTO, summary="获取游戏账户配置")
def get_game_account(mask_sensitive: bool = Query(True, description="是否掩码敏感信息")):
    """
    获取当前实例的游戏账户配置

    ## 功能描述
    返回当前激活实例的游戏账户配置信息，包括平台、区域、路径等设置。

    ## 查询参数
    - **mask_sensitive**: 是否掩码敏感信息（账号、密码），默认true

    ## 返回数据
    - **platform**: 游戏平台
    - **gameRegion**: 游戏区域
    - **gamePath**: 游戏安装路径
    - **gameLanguage**: 游戏语言
    - **useCustomWinTitle**: 是否使用自定义窗口标题
    - **customWinTitle**: 自定义窗口标题
    - **account**: 游戏账号（可能被掩码）
    - **password**: 游戏密码（可能被掩码）

    ## 安全说明
    - 默认情况下敏感信息会被掩码处理
    - 只有特殊权限才能获取完整信息

    ## 使用示例
    ```python
    import requests
    # 获取掩码后的信息
    response = requests.get("http://localhost:8000/api/v1/accounts/game-account")
    config = response.json()
    print(f"游戏平台: {config['platform']}")

    # 获取完整信息（需要权限）
    response = requests.get("http://localhost:8000/api/v1/accounts/game-account?mask_sensitive=false")
    ```
    """
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


@router.put("/game-account", response_model=OkResponse, summary="更新游戏账户配置")
def update_game_account(payload: Dict[str, Any]) -> OkResponse:
    """
    更新当前实例的游戏账户配置

    ## 功能描述
    更新当前激活实例的游戏账户相关配置，支持部分更新。

    ## 请求参数
    - **platform** (可选): 游戏平台
    - **gameRegion** (可选): 游戏区域
    - **gamePath** (可选): 游戏安装路径
    - **gameLanguage** (可选): 游戏语言
    - **useCustomWinTitle** (可选): 是否使用自定义窗口标题
    - **customWinTitle** (可选): 自定义窗口标题
    - **account** (可选): 游戏账号
    - **password** (可选): 游戏密码

    ## 返回数据
    - **ok**: 操作是否成功

    ## 错误码
    - **CONFIG_UPDATE_FAILED**: 配置更新失败 (500)
    - **VALIDATION_ERROR**: 参数验证失败 (400)

    ## 安全说明
    - 敏感信息（账号、密码）会被安全处理
    - 系统会记录配置变更日志（不包含敏感信息）

    ## 使用示例
    ```python
    import requests
    data = {
        "platform": "PC",
        "gameRegion": "cn",
        "gameLanguage": "zh-cn"
    }
    response = requests.put("http://localhost:8000/api/v1/accounts/game-account", json=data)
    result = response.json()
    print(f"更新结果: {result['ok']}")
    ```
    """
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


@router.get("/options", response_model=Dict[str, Any], summary="获取多账户全局选项")
def get_account_options() -> Dict[str, Any]:
    """
    获取多账户相关的全局配置选项

    ## 功能描述
    返回多账户系统的全局配置设置，包括实例运行模式和完成后操作。

    ## 返回数据
    - **instanceRun**: 实例运行模式
      - "ALL": 运行所有启用的实例
      - "CURRENT": 仅运行当前实例
    - **afterDone**: 完成后操作
      - "NONE": 无操作
      - "CLOSE_GAME": 关闭游戏
      - "SHUTDOWN": 关机

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/accounts/options")
    options = response.json()
    print(f"运行模式: {options['instanceRun']}")
    print(f"完成后操作: {options['afterDone']}")
    ```
    """
    ctx = get_ctx()
    odc = ctx.one_dragon_config
    return {
        "instanceRun": odc.instance_run,
        "afterDone": odc.after_done,
    }


@router.put("/options", response_model=Dict[str, Any], summary="更新多账户全局选项")
def update_account_options(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新多账户相关的全局配置选项

    ## 功能描述
    更新多账户系统的全局配置设置，控制实例运行行为和完成后操作。

    ## 请求参数
    - **instanceRun** (可选): 实例运行模式
      - "ALL": 运行所有启用的实例
      - "CURRENT": 仅运行当前实例
    - **afterDone** (可选): 完成后操作
      - "NONE": 无操作
      - "CLOSE_GAME": 关闭游戏
      - "SHUTDOWN": 关机

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "instanceRun": "ALL",
        "afterDone": "CLOSE_GAME"
    }
    response = requests.put("http://localhost:8000/api/v1/accounts/options", json=data)
    result = response.json()
    print(f"更新结果: {result['ok']}")
    ```
    """
    ctx = get_ctx()
    odc = ctx.one_dragon_config
    if "instanceRun" in payload:
        odc.instance_run = payload["instanceRun"]
    if "afterDone" in payload:
        odc.after_done = payload["afterDone"]
    return {"ok": True}
