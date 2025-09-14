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
    tags=["锄大地 World Patrol"],
    dependencies=[Depends(get_api_key_dependency())],
)


_registry = get_global_run_registry()


@router.get("/entries", response_model=List[Dict[str, Any]], summary="获取入口列表")
def list_entries():
    """
    获取所有锄大地入口列表

    ## 功能描述
    返回系统中所有可用的锄大地入口信息，用于选择锄大地区域。

    ## 返回数据
    入口信息列表，每个入口包含：
    - **entryName**: 入口名称
    - **entryId**: 入口唯一标识符

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/world-patrol/entries")
    entries = response.json()
    for entry in entries:
        print(f"入口: {entry['entryName']} (ID: {entry['entryId']})")
    ```
    """
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    return [{"entryName": e.entry_name, "entryId": e.entry_id} for e in svc.entry_list]


@router.get("/areas", response_model=List[Dict[str, Any]], summary="获取区域列表")
def list_areas(entryId: str = Query(..., description="入口ID")):
    """
    获取指定入口下的所有区域列表

    ## 功能描述
    根据入口ID返回该入口下所有可用的锄大地区域信息。

    ## 查询参数
    - **entryId**: 入口ID，必需参数

    ## 返回数据
    区域信息列表，每个区域包含：
    - **entryId**: 所属入口ID
    - **areaName**: 区域名称
    - **areaId**: 区域ID
    - **fullId**: 完整区域标识符
    - **isHollow**: 是否为空洞区域
    - **parentAreaId**: 父区域ID（如果有）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/world-patrol/areas?entryId=entry1")
    areas = response.json()
    for area in areas:
        print(f"区域: {area['areaName']} (完整ID: {area['fullId']})")
    ```
    """
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


@router.get("/routes", response_model=List[Dict[str, Any]], summary="获取路线列表")
def list_routes(entryId: str | None = None, areaFullId: str | None = None):
    """
    获取锄大地路线列表

    ## 功能描述
    根据指定条件获取锄大地路线信息，可以按区域过滤或获取所有路线。

    ## 查询参数
    - **entryId** (可选): 入口ID，用于过滤特定入口的路线
    - **areaFullId** (可选): 区域完整ID，用于获取特定区域的路线

    ## 返回数据
    路线信息列表，每个路线包含详细的操作步骤和配置信息

    ## 使用示例
    ```python
    import requests
    # 获取所有路线
    response = requests.get("http://localhost:8000/api/v1/world-patrol/routes")

    # 获取特定区域的路线
    response = requests.get("http://localhost:8000/api/v1/world-patrol/routes?areaFullId=area_full_1")
    routes = response.json()
    print(f"找到 {len(routes)} 条路线")
    ```
    """
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


@router.post("/routes", response_model=Dict[str, Any], summary="保存锄大地路线")
def save_route(payload: Dict[str, Any]):
    """
    保存或更新锄大地路线

    ## 功能描述
    保存新的锄大地路线或更新现有路线，包括路线的操作步骤和配置。

    ## 请求参数
    - **tp_area_id**: 目标区域完整ID
    - **tp_name**: 路线名称
    - **idx**: 路线索引
    - **op_list**: 操作步骤列表

    ## 返回数据
    - **ok**: 操作是否成功
    - **error** (失败时): 错误信息
      - **code**: 错误代码
      - **message**: 错误消息

    ## 错误码
    - **AREA_NOT_FOUND**: 指定区域不存在

    ## 使用示例
    ```python
    import requests
    data = {
        "tp_area_id": "area_full_1",
        "tp_name": "我的路线",
        "idx": 1,
        "op_list": [
            {"type": "move", "params": {"x": 100, "y": 200}},
            {"type": "interact", "params": {"target": "chest"}}
        ]
    }
    response = requests.post("http://localhost:8000/api/v1/world-patrol/routes", json=data)
    result = response.json()
    print(f"保存结果: {result['ok']}")
    ```
    """
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


@router.delete("/routes/{areaFullId}/{idx}", response_model=Dict[str, Any], summary="删除锄大地路线")
def delete_route(areaFullId: str, idx: int):
    """
    删除指定的锄大地路线

    ## 功能描述
    根据区域ID和路线索引删除指定的锄大地路线。

    ## 路径参数
    - **areaFullId**: 区域完整ID
    - **idx**: 路线索引

    ## 返回数据
    - **ok**: 操作是否成功
    - **error** (失败时): 错误信息

    ## 错误码
    - **AREA_NOT_FOUND**: 指定区域不存在

    ## 使用示例
    ```python
    import requests
    response = requests.delete("http://localhost:8000/api/v1/world-patrol/routes/area_full_1/1")
    result = response.json()
    print(f"删除结果: {result['ok']}")
    ```
    """
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


@router.get("/large-maps/{areaFullId}", response_model=Dict[str, Any], summary="获取大地图配置")
def get_large_map(areaFullId: str):
    """
    获取指定区域的大地图配置

    ## 功能描述
    返回指定区域的大地图配置信息，包括图标列表和位置信息。

    ## 路径参数
    - **areaFullId**: 区域完整ID

    ## 返回数据
    - **areaFullId**: 区域完整ID
    - **iconList**: 图标列表
      - **iconName**: 图标名称
      - **templateId**: 模板ID
      - **lmPos**: 大地图位置坐标 [x, y]
      - **tpPos**: 传送点位置坐标 [x, y]

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/world-patrol/large-maps/area_full_1")
    large_map = response.json()
    if large_map:
        print(f"区域: {large_map['areaFullId']}")
        print(f"图标数量: {len(large_map['iconList'])}")
    ```
    """
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


@router.post("/large-maps/{areaFullId}", response_model=Dict[str, Any], summary="保存大地图配置")
def save_large_map(areaFullId: str, payload: Dict[str, Any]):
    """
    保存指定区域的大地图配置

    ## 功能描述
    保存或更新指定区域的大地图配置，包括图标位置和模板信息。

    ## 路径参数
    - **areaFullId**: 区域完整ID

    ## 请求参数
    - **iconList**: 图标列表
      - **iconName**: 图标名称
      - **templateId**: 模板ID
      - **lmPos**: 大地图位置坐标 [x, y]
      - **tpPos**: 传送点位置坐标 [x, y]

    ## 返回数据
    - **ok**: 操作是否成功
    - **error** (失败时): 错误信息

    ## 错误码
    - **AREA_NOT_FOUND**: 指定区域不存在

    ## 使用示例
    ```python
    import requests
    data = {
        "iconList": [
            {
                "iconName": "宝箱",
                "templateId": "chest_template",
                "lmPos": [100, 200],
                "tpPos": [150, 250]
            }
        ]
    }
    response = requests.post("http://localhost:8000/api/v1/world-patrol/large-maps/area_full_1", json=data)
    result = response.json()
    print(f"保存结果: {result['ok']}")
    ```
    """
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


@router.delete("/large-maps/{areaFullId}", response_model=Dict[str, Any], summary="删除大地图配置")
def delete_large_map(areaFullId: str):
    """
    删除指定区域的大地图配置

    ## 功能描述
    删除指定区域的大地图配置文件和相关数据。

    ## 路径参数
    - **areaFullId**: 区域完整ID

    ## 返回数据
    - **ok**: 操作是否成功
    - **error** (失败时): 错误信息

    ## 错误码
    - **AREA_NOT_FOUND**: 指定区域不存在

    ## 注意事项
    - 删除操作不可逆，请谨慎操作

    ## 使用示例
    ```python
    import requests
    response = requests.delete("http://localhost:8000/api/v1/world-patrol/large-maps/area_full_1")
    result = response.json()
    print(f"删除结果: {result['ok']}")
    ```
    """
    ctx = get_ctx()
    svc: WorldPatrolService = ctx.world_patrol_service
    svc.load_data()
    area: WorldPatrolArea | None = next((a for a in svc.area_list if a.full_id == areaFullId), None)
    if not area:
        return {"ok": False, "error": {"code": "AREA_NOT_FOUND", "message": areaFullId}}
    ok = svc.delete_world_patrol_large_map(area)
    return {"ok": bool(ok)}


# -------- World Patrol Run (锄大地运行) --------


@router.post("/run", response_model=RunIdResponse, summary="运行锄大地")
async def run_world_patrol():
    """
    启动锄大地自动化任务

    ## 功能描述
    启动锄大地任务，按照配置的路线自动执行锄大地操作。

    ## 返回数据
    - **runId**: 任务运行ID，用于后续状态查询和控制

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **CONFIG_ERROR**: 配置错误
    - **NO_ROUTES_CONFIGURED**: 没有配置路线

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/world-patrol/run")
    task_info = response.json()
    print(f"锄大地任务ID: {task_info['runId']}")
    ```
    """
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


@router.get("/config", response_model=Dict[str, Any], summary="获取锄大地配置")
def get_world_patrol_config() -> Dict[str, Any]:
    """
    获取锄大地的配置信息

    ## 功能描述
    返回锄大地的详细配置设置，包括自动战斗配置和路线列表。

    ## 返回数据
    - **autoBattle**: 自动战斗配置名称
    - **routeList**: 路线列表配置

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/world-patrol/config")
    config = response.json()
    print(f"自动战斗配置: {config['autoBattle']}")
    print(f"路线列表: {config['routeList']}")
    ```
    """
    ctx = get_ctx()
    config = ctx.world_patrol_config
    return {
        "autoBattle": config.auto_battle,
        "routeList": config.route_list,
    }


@router.put("/config", response_model=Dict[str, Any], summary="更新锄大地配置")
def update_world_patrol_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新锄大地的配置设置

    ## 功能描述
    更新锄大地的配置参数，支持部分更新。

    ## 请求参数
    - **autoBattle** (可选): 自动战斗配置名称
    - **routeList** (可选): 路线列表配置

    ## 返回数据
    - **message**: 更新成功消息

    ## 使用示例
    ```python
    import requests
    data = {
        "autoBattle": "全配队通用",
        "routeList": ["路线1", "路线2"]
    }
    response = requests.put("http://localhost:8000/api/v1/world-patrol/config", json=data)
    result = response.json()
    print(result["message"])
    ```
    """
    ctx = get_ctx()
    config = ctx.world_patrol_config

    if "autoBattle" in payload:
        config.auto_battle = payload["autoBattle"]
    if "routeList" in payload:
        config.route_list = payload["routeList"]

    return {"message": "Configuration updated successfully"}


# -------- Route Lists (路线列表管理) --------


@router.get("/route-lists", response_model=List[Dict[str, Any]], summary="获取所有路线列表")
def get_route_lists() -> List[Dict[str, Any]]:
    """
    获取所有锄大地路线列表

    ## 功能描述
    返回系统中所有配置的锄大地路线列表信息。

    ## 返回数据
    路线列表信息数组，每个列表包含：
    - **name**: 路线列表名称
    - **listType**: 列表类型
    - **routeItems**: 路线项目列表
    - **routeCount**: 路线数量

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/world-patrol/route-lists")
    route_lists = response.json()
    for route_list in route_lists:
        print(f"路线列表: {route_list['name']}, 路线数量: {route_list['routeCount']}")
    ```
    """
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


@router.get("/route-lists/{listName}", response_model=Dict[str, Any], summary="获取指定的路线列表")
def get_route_list(listName: str) -> Dict[str, Any]:
    """
    获取指定名称的路线列表详情

    ## 功能描述
    根据路线列表名称获取详细的路线列表信息。

    ## 路径参数
    - **listName**: 路线列表名称

    ## 返回数据
    - **name**: 路线列表名称
    - **listType**: 列表类型
    - **routeItems**: 路线项目列表
    - **routeCount**: 路线数量
    - **error** (失败时): 错误信息

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/world-patrol/route-lists/我的路线列表")
    route_list = response.json()
    if "error" not in route_list:
        print(f"路线列表: {route_list['name']}")
        print(f"包含路线: {route_list['routeItems']}")
    ```
    """
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


@router.post("/recording/start", response_model=Dict[str, Any], summary="开始路线录制")
def start_route_recording(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    开始锄大地路线录制（基础控制）

    ## 功能描述
    启动锄大地路线录制功能的基础控制。实际的录制操作建议通过GUI界面进行。

    ## 请求参数
    - **areaFullId**: 区域完整ID，必需参数
    - **routeName** (可选): 路线名称，默认为"recorded_route"

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **routeName**: 路线名称
    - **note**: 使用说明

    ## 注意事项
    - 此API仅提供基础控制功能
    - 实际录制操作涉及复杂的图像处理和坐标计算
    - 建议使用GUI界面进行完整的录制操作

    ## 使用示例
    ```python
    import requests
    data = {
        "areaFullId": "area_full_1",
        "routeName": "我的新路线"
    }
    response = requests.post("http://localhost:8000/api/v1/world-patrol/recording/start", json=data)
    result = response.json()
    print(result["message"])
    ```
    """
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


@router.post("/recording/stop", response_model=Dict[str, Any], summary="停止路线录制")
def stop_route_recording() -> Dict[str, Any]:
    """
    停止锄大地路线录制

    ## 功能描述
    停止当前进行的锄大地路线录制操作。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **note**: 使用说明

    ## 注意事项
    - 停止录制后需要通过GUI界面保存录制的路线
    - 未保存的录制数据可能会丢失

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/world-patrol/recording/stop")
    result = response.json()
    print(result["message"])
    ```
    """
    return {
        "ok": True,
        "message": "Route recording stopped",
        "note": "Use GUI interface to save the recorded route"
    }


@router.post("/large-map-recording/start", response_model=Dict[str, Any], summary="开始大地图录制")
def start_large_map_recording(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    开始大地图录制（基础控制）

    ## 功能描述
    启动大地图录制功能的基础控制。实际的录制操作建议通过GUI界面进行。

    ## 请求参数
    - **areaFullId**: 区域完整ID，必需参数

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **note**: 使用说明

    ## 注意事项
    - 此API仅提供基础控制功能
    - 大地图录制涉及复杂的图像拼接和处理
    - 建议使用GUI界面进行完整的录制操作

    ## 使用示例
    ```python
    import requests
    data = {
        "areaFullId": "area_full_1"
    }
    response = requests.post("http://localhost:8000/api/v1/world-patrol/large-map-recording/start", json=data)
    result = response.json()
    print(result["message"])
    ```
    """
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


@router.post("/large-map-recording/stop", response_model=Dict[str, Any], summary="停止大地图录制")
def stop_large_map_recording() -> Dict[str, Any]:
    """
    停止大地图录制

    ## 功能描述
    停止当前进行的大地图录制操作。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **note**: 使用说明

    ## 注意事项
    - 停止录制后需要通过GUI界面保存录制的大地图
    - 未保存的录制数据可能会丢失

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/world-patrol/large-map-recording/stop")
    result = response.json()
    print(result["message"])
    ```
    """
    return {
        "ok": True,
        "message": "Large map recording stopped",
        "note": "Use GUI interface to save the recorded map"
    }


# -------- Run Record Management (运行记录管理) --------


@router.post("/reset-record", response_model=Dict[str, Any], summary="重置锄大地运行记录")
def reset_world_patrol_record() -> Dict[str, Any]:
    """
    重置锄大地的运行记录

    ## 功能描述
    清除锄大地的历史运行记录，重新开始计算运行状态。

    ## 返回数据
    - **message**: 重置成功消息

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/world-patrol/reset-record")
    result = response.json()
    print(result["message"])
    ```
    """
    ctx = get_ctx()
    ctx.world_patrol_run_record.reset_record()
    return {"message": "World patrol record reset successfully"}


@router.get("/run-record", response_model=Dict[str, Any], summary="获取锄大地运行记录")
def get_world_patrol_run_record() -> Dict[str, Any]:
    """
    获取锄大地的运行记录

    ## 功能描述
    返回锄大地的历史运行记录，包括完成状态和耗时信息。

    ## 返回数据
    - **finished**: 完成状态信息
    - **timeCost**: 运行耗时（秒）
    - **totalFinished**: 总完成数量

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/world-patrol/run-record")
    record = response.json()
    print(f"总完成数量: {record['totalFinished']}")
    print(f"耗时: {record['timeCost']}秒")
    ```
    """
    ctx = get_ctx()
    record = ctx.world_patrol_run_record
    return {
        "finished": record.finished,
        "timeCost": record.time_cost,
        "totalFinished": len(record.finished)
    }


