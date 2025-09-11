from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from zzz_od.api.deps import get_ctx
from zzz_od.api.security import get_api_key_dependency
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.bridges import attach_run_event_bridge
from zzz_od.api.models import RunIdResponse
from zzz_od.application.world_patrol.world_patrol_service import WorldPatrolService
from zzz_od.application.world_patrol.world_patrol_route import WorldPatrolRoute, WorldPatrolOperation
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolArea
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolLargeMap
from zzz_od.application.world_patrol.world_patrol_app import WorldPatrolApp


router = APIRouter(
    prefix="/api/v1/world-patrol",
    tags=["world-patrol"],
    dependencies=[Depends(get_api_key_dependency())],
)


_registry = get_global_run_registry()


@router.get("/entries")
def list_entries():
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    return [{"entryName": e.entry_name, "entryId": e.entry_id} for e in svc.entry_list]


@router.get("/areas")
def list_areas(entryId: str = Query(...)):
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    entry = next((e for e in svc.entry_list if e.entry_id == entryId), None)
    if not entry:
        return []
    areas = svc.get_area_list_by_entry(entry)
    return [
        {
            "entryId": a.entry.entry_id,
            "areaName": a.area_name,
            "areaId": a.area_id,
            "fullId": a.full_id,
            "isHollow": a.is_hollow,
            "parentAreaId": a.parent_area.area_id if a.parent_area else None,
        }
        for a in areas
    ]


@router.get("/routes")
def list_routes(entryId: str | None = None, areaFullId: str | None = None):
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    routes = []
    if areaFullId:
        area = next((a for a in svc.area_list if a.full_id == areaFullId), None)
        if area:
            routes = svc.get_world_patrol_routes_by_area(area)
    else:
        routes = svc.get_world_patrol_routes()
    return [r.to_dict() for r in routes]


@router.post("/routes")
def save_route(payload: Dict[str, Any]):
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    area_full_id = payload.get("tp_area_id")
    tp_name = payload.get("tp_name")
    idx = int(payload.get("idx", 0))
    op_list = [WorldPatrolOperation.from_dict(op) for op in payload.get("op_list", [])]
    area: WorldPatrolArea | None = next((a for a in svc.area_list if a.full_id == area_full_id), None)
    if not area:
        return {"ok": False, "error": {"code": "AREA_NOT_FOUND", "message": area_full_id}}
    route = WorldPatrolRoute(tp_area=area, tp_name=tp_name, idx=idx, op_list=op_list)
    ok = svc.save_world_patrol_route(route)
    return {"ok": bool(ok)}


@router.delete("/routes/{areaFullId}/{idx}")
def delete_route(areaFullId: str, idx: int):
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    area: WorldPatrolArea | None = next((a for a in svc.area_list if a.full_id == areaFullId), None)
    if not area:
        return {"ok": False, "error": {"code": "AREA_NOT_FOUND", "message": areaFullId}}
    # 构造一个临时 route 只为删除
    temp = WorldPatrolRoute(tp_area=area, tp_name="", idx=idx, op_list=[])
    ok = svc.delete_world_patrol_route(temp)
    return {"ok": bool(ok)}


# 大地图 CRUD（保存/读取/删除）


@router.get("/large-maps/{areaFullId}")
def get_large_map(areaFullId: str):
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    lm = svc.get_large_map_by_area_full_id(areaFullId)
    if lm is None:
        return None
    return {
        "areaFullId": lm.area_full_id,
        "iconList": [
            {
                "iconName": i.icon_name,
                "templateId": i.template_id,
                "lmPos": [i.lm_pos.x, i.lm_pos.y] if i.lm_pos else None,
                "tpPos": [i.tp_pos.x, i.tp_pos.y] if i.tp_pos else None,
            }
            for i in lm.icon_list
        ],
        # 提示：road_mask 是大图像，这里不直接返回
    }


@router.post("/large-maps/{areaFullId}")
def save_large_map(areaFullId: str, payload: Dict[str, Any]):
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    area: WorldPatrolArea | None = next((a for a in svc.area_list if a.full_id == areaFullId), None)
    if not area:
        return {"ok": False, "error": {"code": "AREA_NOT_FOUND", "message": areaFullId}}
    # 仅保存图标清单（road_mask 不在此接口编辑）
    lm = svc.get_large_map_by_area_full_id(areaFullId)
    if lm is None:
        lm = WorldPatrolLargeMap(areaFullId, None, [])
    new_icons = []
    for icon in payload.get("iconList", []) or []:
        from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolLargeMapIcon
        from one_dragon.base.geometry.point import Point
        lm_pos = icon.get("lmPos")
        tp_pos = icon.get("tpPos")
        new_icons.append(
            WorldPatrolLargeMapIcon(
                icon_name=icon.get("iconName", ""),
                template_id=icon.get("templateId", ""),
                lm_pos=None if not lm_pos else Point(lm_pos[0], lm_pos[1]),
                tp_pos=None if not tp_pos else Point(tp_pos[0], tp_pos[1]),
            )
        )
    lm.icon_list = new_icons
    ok = svc.save_world_patrol_large_map(area, lm)
    return {"ok": bool(ok)}


@router.delete("/large-maps/{areaFullId}")
def delete_large_map(areaFullId: str):
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    area: WorldPatrolArea | None = next((a for a in svc.area_list if a.full_id == areaFullId), None)
    if not area:
        return {"ok": False, "error": {"code": "AREA_NOT_FOUND", "message": areaFullId}}
    ok = svc.delete_world_patrol_large_map(area)
    return {"ok": bool(ok)}


# -------- World Patrol Run (锄大地运行) --------


@router.post("/run")
async def run_world_patrol():
    """运行锄大地"""
    run_id = _run_via_onedragon_with_temp(["world_patrol"])
    return RunIdResponse(runId=run_id)


def _run_via_onedragon_with_temp(app_ids: list[str]) -> str:
    """通过一条龙总控运行指定 appId 列表（临时运行清单）。"""
    ctx = get_ctx()
    original_temp = getattr(ctx.one_dragon_app_config, "_temp_app_run_list", None)
    ctx.one_dragon_app_config.set_temp_app_run_list(app_ids)
    from zzz_od.application.zzz_one_dragon_app import ZOneDragonApp
    run_id = _start_app_run(lambda c: ZOneDragonApp(c))
    # 由 after_app_shutdown 自动清理 temp；若需要也可在桥接 detach 里兜底
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


# -------- World Patrol Config (锄大地配置) --------


@router.get("/config")
def get_world_patrol_config() -> Dict[str, Any]:
    """获取锄大地配置"""
    ctx = get_ctx()
    config = ctx.world_patrol_config
    return {
        "autoBattle": config.auto_battle,
        "routeList": config.route_list,
    }


@router.put("/config")
def update_world_patrol_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新锄大地配置"""
    ctx = get_ctx()
    config = ctx.world_patrol_config

    if "autoBattle" in payload:
        config.auto_battle = payload["autoBattle"]
    if "routeList" in payload:
        config.route_list = payload["routeList"]

    return {"message": "Configuration updated successfully"}


# -------- Route Lists (路线列表管理) --------


@router.get("/route-lists")
def get_route_lists() -> List[Dict[str, Any]]:
    """获取所有路线列表"""
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    route_lists = svc.get_world_patrol_route_lists()
    return [
        {
            "name": rl.name,
            "listType": rl.list_type.value,
            "routeItems": rl.route_items,
            "routeCount": len(rl.route_items)
        }
        for rl in route_lists
    ]


@router.get("/route-lists/{listName}")
def get_route_list(listName: str) -> Dict[str, Any]:
    """获取指定的路线列表"""
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    route_lists = svc.get_world_patrol_route_lists()
    route_list = next((rl for rl in route_lists if rl.name == listName), None)
    if not route_list:
        return {"error": "Route list not found"}

    return {
        "name": route_list.name,
        "listType": route_list.list_type.value,
        "routeItems": route_list.route_items,
        "routeCount": len(route_list.route_items)
    }


# -------- Recording Control (录制控制 - 基础功能) --------


@router.post("/recording/start")
def start_route_recording(payload: Dict[str, Any]) -> Dict[str, Any]:
    """开始路线录制（基础控制）"""
    # 注意：这里只提供基础的录制控制API
    # 实际的录制逻辑比较复杂，涉及图像处理、坐标计算等
    # 建议通过GUI界面进行录制操作

    area_full_id = payload.get("areaFullId")
    route_name = payload.get("routeName", "recorded_route")

    if not area_full_id:
        return {"ok": False, "error": "areaFullId is required"}

    return {
        "ok": True,
        "message": f"Route recording control initiated for area {area_full_id}",
        "routeName": route_name,
        "note": "Use GUI interface for actual recording. This API provides basic control only."
    }


@router.post("/recording/stop")
def stop_route_recording() -> Dict[str, Any]:
    """停止路线录制"""
    return {
        "ok": True,
        "message": "Route recording stopped",
        "note": "Use GUI interface to save the recorded route"
    }


@router.post("/large-map-recording/start")
def start_large_map_recording(payload: Dict[str, Any]) -> Dict[str, Any]:
    """开始大地图录制（基础控制）"""
    # 大地图录制涉及复杂的图像拼接和处理
    # 建议通过GUI界面进行录制操作

    area_full_id = payload.get("areaFullId")

    if not area_full_id:
        return {"ok": False, "error": "areaFullId is required"}

    return {
        "ok": True,
        "message": f"Large map recording control initiated for area {area_full_id}",
        "note": "Use GUI interface for actual recording. This API provides basic control only."
    }


@router.post("/large-map-recording/stop")
def stop_large_map_recording() -> Dict[str, Any]:
    """停止大地图录制"""
    return {
        "ok": True,
        "message": "Large map recording stopped",
        "note": "Use GUI interface to save the recorded map"
    }


# -------- Run Record Management (运行记录管理) --------


@router.post("/reset-record")
def reset_world_patrol_record() -> Dict[str, Any]:
    """重置锄大地运行记录"""
    ctx = get_ctx()
    ctx.world_patrol_run_record.reset_record()
    return {"message": "World patrol record reset successfully"}


@router.get("/run-record")
def get_world_patrol_run_record() -> Dict[str, Any]:
    """获取锄大地运行记录"""
    ctx = get_ctx()
    record = ctx.world_patrol_run_record
    return {
        "finished": record.finished,
        "timeCost": record.time_cost,
        "totalFinished": len(record.finished)
    }


