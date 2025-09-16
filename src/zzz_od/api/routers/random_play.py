from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from zzz_od.api.deps import get_ctx
from zzz_od.api.security import get_api_key_dependency
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.bridges import attach_run_event_bridge
from zzz_od.api.models import RunIdResponse


router = APIRouter(
    prefix="/api/v1/random-play",
    tags=["录像店 Random Play"],
    dependencies=[Depends(get_api_key_dependency())],
)


_registry = get_global_run_registry()


@router.get("/config", response_model=Dict[str, Any], summary="获取录像店配置")
def get_random_play_config() -> Dict[str, Any]:
    """
    获取录像店营业的配置信息

    ## 功能描述
    返回录像店营业的配置设置，包括代理人选择配置。

    ## 返回数据
    - **agentName1**: 第一个代理人名称
    - **agentName2**: 第二个代理人名称

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/random-play/config")
    config = response.json()
    print(f"代理人1: {config['agentName1']}")
    print(f"代理人2: {config['agentName2']}")
    ```
    """
    ctx = get_ctx()
    config = ctx.random_play_config
    return {
        "agentName1": config.agent_name_1,
        "agentName2": config.agent_name_2,
    }


@router.put("/config", response_model=Dict[str, Any], summary="更新录像店配置")
def update_random_play_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新录像店营业的配置设置

    ## 功能描述
    更新录像店营业的配置参数，支持部分更新。

    ## 请求参数
    - **agentName1** (可选): 第一个代理人名称
    - **agentName2** (可选): 第二个代理人名称

    ## 返回数据
    - **message**: 更新成功消息

    ## 使用示例
    ```python
    import requests
    data = {
        "agentName1": "妮可",
        "agentName2": "艾莲"
    }
    response = requests.put("http://localhost:8000/api/v1/random-play/config", json=data)
    result = response.json()
    print(result["message"])
    ```
    """
    ctx = get_ctx()
    config = ctx.random_play_config

    if "agentName1" in payload:
        config.agent_name_1 = payload["agentName1"]
    if "agentName2" in payload:
        config.agent_name_2 = payload["agentName2"]

    return {"message": "Configuration updated successfully"}


@router.post("/run", response_model=RunIdResponse, summary="运行录像店营业")
async def run_random_play():
    """
    启动录像店营业自动化任务

    ## 功能描述
    启动录像店营业任务，自动完成录像店的营业流程。

    ## 返回数据
    - **runId**: 任务运行ID，用于后续状态查询和控制

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **CONFIG_ERROR**: 配置错误

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/random-play/run")
    task_info = response.json()
    print(f"录像店任务ID: {task_info['runId']}")
    ```
    """
    run_id = _run_via_onedragon_with_temp(["random_play"])
    return RunIdResponse(runId=run_id)


@router.post("/reset-record", response_model=Dict[str, Any], summary="重置录像店运行记录")
def reset_random_play_record() -> Dict[str, Any]:
    """
    重置录像店营业的运行记录

    ## 功能描述
    清除录像店营业的历史运行记录，重新开始计算运行状态。

    ## 返回数据
    - **message**: 重置成功消息

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/random-play/reset-record")
    result = response.json()
    print(result["message"])
    ```
    """
    ctx = get_ctx()
    ctx.random_play_run_record.reset_record()
    return {"message": "Random play record reset successfully"}


@router.get("/run-record", response_model=Dict[str, Any], summary="获取录像店运行记录")
def get_random_play_run_record() -> Dict[str, Any]:
    """
    获取录像店营业的运行记录

    ## 功能描述
    返回录像店营业的历史运行记录，包括完成状态和耗时信息。

    ## 返回数据
    - **finished**: 是否已完成，布尔值
    - **status**: 运行状态（0=未运行，1=成功，2=失败，3=运行中）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/random-play/run-record")
    record = response.json()
    print(f"完成状态: {record['finished']}")
    print(f"运行状态: {record['status']}")
    ```
    """
    ctx = get_ctx()
    record = ctx.random_play_run_record
    return {
        "finished": record.run_status == record.STATUS_SUCCESS,
        "status": record.run_status_under_now
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