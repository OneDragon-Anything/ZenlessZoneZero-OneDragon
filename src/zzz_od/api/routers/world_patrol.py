from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from zzz_od.api.deps import get_ctx
from zzz_od.api.security import get_api_key_dependency
from zzz_od.application.world_patrol.world_patrol_service import WorldPatrolService
from zzz_od.application.world_patrol.world_patrol_route import WorldPatrolRoute, WorldPatrolOperation
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolArea
from zzz_od.application.world_patrol.world_patrol_area import WorldPatrolLargeMap


router = APIRouter(
    prefix="/api/v1/world-patrol",
    tags=["world-patrol"],
    dependencies=[Depends(get_api_key_dependency())],
)


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


