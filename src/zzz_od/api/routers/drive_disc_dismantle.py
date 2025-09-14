from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from zzz_od.api.deps import get_ctx
from zzz_od.api.security import get_api_key_dependency
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.bridges import attach_run_event_bridge
from zzz_od.api.models import RunIdResponse


router = APIRouter(
    prefix="/api/v1/drive-disc-dismantle",
    tags=["驱动盘拆解 Drive Disc Dismantle"],
    dependencies=[Depends(get_api_key_dependency())],
)


_registry = get_global_run_registry()


@router.get("/config", response_model=Dict[str, Any], summary="获取驱动盘拆解配置")
def get_drive_disc_dismantle_config() -> Dict[str, Any]:
    """
    获取驱动盘拆解的配置信息

    ## 功能描述
    返回驱动盘拆解的配置设置，包括拆解等级和是否拆解废弃驱动盘。

    ## 返回数据
    - **dismantleLevel**: 拆解等级设置
    - **dismantleAbandon**: 是否拆解废弃驱动盘，布尔值

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/drive-disc-dismantle/config")
    config = response.json()
    print(f"拆解等级: {config['dismantleLevel']}")
    print(f"拆解废弃: {config['dismantleAbandon']}")
    ```
    """
    ctx = get_ctx()
    config = ctx.drive_disc_dismantle_config
    return {
        "dismantleLevel": config.dismantle_level,
        "dismantleAbandon": config.dismantle_abandon,
    }


@router.put("/config", response_model=Dict[str, Any], summary="更新驱动盘拆解配置")
def update_drive_disc_dismantle_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新驱动盘拆解的配置设置

    ## 功能描述
    更新驱动盘拆解的配置参数，支持部分更新。

    ## 请求参数
    - **dismantleLevel** (可选): 拆解等级设置
    - **dismantleAbandon** (可选): 是否拆解废弃驱动盘，布尔值

    ## 返回数据
    - **message**: 更新成功消息

    ## 使用示例
    ```python
    import requests
    data = {
        "dismantleLevel": "B级及以下",
        "dismantleAbandon": True
    }
    response = requests.put("http://localhost:8000/api/v1/drive-disc-dismantle/config", json=data)
    result = response.json()
    print(result["message"])
    ```
    """
    ctx = get_ctx()
    config = ctx.drive_disc_dismantle_config

    if "dismantleLevel" in payload:
        config.dismantle_level = payload["dismantleLevel"]
    if "dismantleAbandon" in payload:
        config.dismantle_abandon = payload["dismantleAbandon"]

    return {"message": "Configuration updated successfully"}


@router.post("/run", response_model=RunIdResponse, summary="运行驱动盘拆解")
async def run_drive_disc_dismantle():
    """
    启动驱动盘拆解自动化任务

    ## 功能描述
    启动驱动盘拆解任务，根据配置自动拆解指定等级的驱动盘。

    ## 返回数据
    - **runId**: 任务运行ID，用于后续状态查询和控制

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **CONFIG_ERROR**: 配置错误
    - **NO_DISCS_TO_DISMANTLE**: 没有可拆解的驱动盘

    ## 注意事项
    - 拆解操作不可逆，请确认配置正确
    - 建议先备份重要的驱动盘

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/drive-disc-dismantle/run")
    task_info = response.json()
    print(f"驱动盘拆解任务ID: {task_info['runId']}")
    ```
    """
    run_id = _run_via_onedragon_with_temp(["drive_disc_dismantle"])
    return RunIdResponse(runId=run_id)


@router.post("/reset-record", response_model=Dict[str, Any], summary="重置驱动盘拆解运行记录")
def reset_drive_disc_dismantle_record() -> Dict[str, Any]:
    """
    重置驱动盘拆解的运行记录

    ## 功能描述
    清除驱动盘拆解的历史运行记录，重新开始计算运行状态。

    ## 返回数据
    - **message**: 重置成功消息

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/drive-disc-dismantle/reset-record")
    result = response.json()
    print(result["message"])
    ```
    """
    ctx = get_ctx()
    ctx.drive_disc_dismantle_record.reset_record()
    return {"message": "Drive disc dismantle record reset successfully"}


@router.get("/run-record", response_model=Dict[str, Any], summary="获取驱动盘拆解运行记录")
def get_drive_disc_dismantle_run_record() -> Dict[str, Any]:
    """
    获取驱动盘拆解的运行记录

    ## 功能描述
    返回驱动盘拆解的历史运行记录，包括完成状态和耗时信息。

    ## 返回数据
    - **finished**: 是否已完成，布尔值
    - **timeCost**: 运行耗时（秒）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/drive-disc-dismantle/run-record")
    record = response.json()
    print(f"完成状态: {record['finished']}")
    print(f"耗时: {record['timeCost']}秒")
    ```
    """
    ctx = get_ctx()
    record = ctx.drive_disc_dismantle_record
    return {
        "finished": record.finished,
        "timeCost": record.time_cost,
    }


@router.get("/dismantle-levels", response_model=Dict[str, Any], summary="获取可选的拆解等级")
def get_dismantle_levels() -> Dict[str, Any]:
    """
    获取所有可选的驱动盘拆解等级

    ## 功能描述
    返回系统支持的所有驱动盘拆解等级选项，用于配置界面的选择。

    ## 返回数据
    - **levels**: 拆解等级选项列表
      - **value**: 等级值
      - **label**: 等级显示名称

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/drive-disc-dismantle/dismantle-levels")
    levels = response.json()
    for level in levels['levels']:
        print(f"等级: {level['label']} (值: {level['value']})")
    ```
    """
    from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_config import DismantleLevelEnum
    return {
        "levels": [
            {"value": level.value.value, "label": level.value.value}
            for level in DismantleLevelEnum
        ]
    }


def _run_via_onedragon_with_temp(app_ids: list[str]) -> str:
    """通过一条龙总控运行指定 appId 列表（临时运行清单）。"""
    ctx = get_ctx()
    original_temp = getattr(ctx.one_dragon_app_config, "_temp_app_run_list", None)
    ctx.one_dragon_app_config.set_temp_app_run_list(app_ids)
    from zzz_od.application.zzz_one_dragon_app import ZOneDragonApp
    run_id = _start_app_run(lambda c: ZOneDragonApp(c))
    return run_id


def _start_app_run(app_factory) -> str:
    ctx = get_ctx()
    registry = get_global_run_registry()

    def _factory_task():
        import asyncio

        async def runner():
            loop = asyncio.get_running_loop()
            def _exec():
                app = app_factory(ctx)
                app.execute()
            return await loop.run_in_executor(None, _exec)

        return asyncio.create_task(runner())

    run_id = registry.create(_factory_task)
    attach_run_event_bridge(ctx, run_id)
    return run_id