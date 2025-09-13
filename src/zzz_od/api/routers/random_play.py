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
    tags=["random-play"],
    dependencies=[Depends(get_api_key_dependency())],
)


_registry = get_global_run_registry()


@router.get("/config")
def get_random_play_config() -> Dict[str, Any]:
    """获取影像店配置"""
    ctx = get_ctx()
    config = ctx.random_play_config
    return {
        "agentName1": config.agent_name_1,
        "agentName2": config.agent_name_2,
    }


@router.put("/config")
def update_random_play_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新影像店配置"""
    ctx = get_ctx()
    config = ctx.random_play_config

    if "agentName1" in payload:
        config.agent_name_1 = payload["agentName1"]
    if "agentName2" in payload:
        config.agent_name_2 = payload["agentName2"]

    return {"message": "Configuration updated successfully"}


@router.post("/run")
async def run_random_play():
    """运行影像店营业"""
    run_id = _run_via_onedragon_with_temp(["random_play"])
    return RunIdResponse(runId=run_id)


@router.post("/reset-record")
def reset_random_play_record() -> Dict[str, Any]:
    """重置影像店运行记录"""
    ctx = get_ctx()
    ctx.random_play_run_record.reset_record()
    return {"message": "Random play record reset successfully"}


@router.get("/run-record")
def get_random_play_run_record() -> Dict[str, Any]:
    """获取影像店运行记录"""
    ctx = get_ctx()
    record = ctx.random_play_run_record
    return {
        "finished": record.finished,
        "timeCost": record.time_cost,
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