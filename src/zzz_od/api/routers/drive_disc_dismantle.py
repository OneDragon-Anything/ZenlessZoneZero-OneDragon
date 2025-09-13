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
    tags=["drive-disc-dismantle"],
    dependencies=[Depends(get_api_key_dependency())],
)


_registry = get_global_run_registry()


@router.get("/config")
def get_drive_disc_dismantle_config() -> Dict[str, Any]:
    """获取驱动盘拆解配置"""
    ctx = get_ctx()
    config = ctx.drive_disc_dismantle_config
    return {
        "dismantleLevel": config.dismantle_level,
        "dismantleAbandon": config.dismantle_abandon,
    }


@router.put("/config")
def update_drive_disc_dismantle_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新驱动盘拆解配置"""
    ctx = get_ctx()
    config = ctx.drive_disc_dismantle_config

    if "dismantleLevel" in payload:
        config.dismantle_level = payload["dismantleLevel"]
    if "dismantleAbandon" in payload:
        config.dismantle_abandon = payload["dismantleAbandon"]

    return {"message": "Configuration updated successfully"}


@router.post("/run")
async def run_drive_disc_dismantle():
    """运行驱动盘拆解"""
    run_id = _run_via_onedragon_with_temp(["drive_disc_dismantle"])
    return RunIdResponse(runId=run_id)


@router.post("/reset-record")
def reset_drive_disc_dismantle_record() -> Dict[str, Any]:
    """重置驱动盘拆解运行记录"""
    ctx = get_ctx()
    ctx.drive_disc_dismantle_record.reset_record()
    return {"message": "Drive disc dismantle record reset successfully"}


@router.get("/run-record")
def get_drive_disc_dismantle_run_record() -> Dict[str, Any]:
    """获取驱动盘拆解运行记录"""
    ctx = get_ctx()
    record = ctx.drive_disc_dismantle_record
    return {
        "finished": record.finished,
        "timeCost": record.time_cost,
    }


@router.get("/dismantle-levels")
def get_dismantle_levels() -> Dict[str, Any]:
    """获取可选的拆解等级"""
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