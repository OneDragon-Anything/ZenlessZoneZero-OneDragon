from __future__ import annotations

import asyncio
from typing import Dict, List

from fastapi import APIRouter, Depends

from zzz_od.api.deps import get_ctx
from zzz_od.api.models import RunIdResponse, RunStatusResponse, RunStatusEnum
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.security import get_api_key_dependency
from zzz_od.api.bridges import attach_run_event_bridge
from zzz_od.api.status_builder import build_onedragon_aggregate
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntConfig
from zzz_od.application.coffee.coffee_config import CoffeeConfig
from zzz_od.application.shiyu_defense.shiyu_defense_config import ShiyuDefenseConfig
from zzz_od.game_data.agent import DmgTypeEnum
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.bridges import attach_run_event_bridge


router = APIRouter(
    prefix="/api/v1/onedragon",
    tags=["onedragon"],
    dependencies=[Depends(get_api_key_dependency())],
)


_registry = get_global_run_registry()


@router.post("/run", response_model=RunIdResponse)
def onedragon_run() -> RunIdResponse:
    ctx = get_ctx()

    def _factory() -> asyncio.Task:
        async def runner():
            loop = asyncio.get_running_loop()
            from zzz_od.application.zzz_one_dragon_app import ZOneDragonApp

            def _exec():
                app = ZOneDragonApp(ctx)
                app.execute()

            await loop.run_in_executor(None, _exec)

        return asyncio.create_task(runner())

    run_id = _registry.create(_factory)
    # attach event bridge for WS and status message updates
    attach_run_event_bridge(ctx, run_id)
    return RunIdResponse(runId=run_id)


@router.post("/run/{run_id}:cancel")
async def onedragon_cancel(run_id: str):
    _registry.cancel(run_id)
    ctx = get_ctx()
    ctx.stop_running()
    return {"ok": True}


# -------- Charge plan --------


@router.get("/charge-plan")
def get_charge_plan():
    ctx = get_ctx()
    cc = ctx.charge_plan_config
    items = [
        {
            "tabName": p.tab_name,
            "categoryName": p.category_name,
            "missionTypeName": p.mission_type_name,
            "missionName": p.mission_name,
            "level": p.level,
            "autoBattleConfig": p.auto_battle_config,
            "runTimes": p.run_times,
            "planTimes": p.plan_times,
            "cardNum": p.card_num,
            "predefinedTeamIdx": p.predefined_team_idx,
            "notoriousHuntBuffNum": p.notorious_hunt_buff_num,
            "planId": p.plan_id,
        }
        for p in cc.plan_list
    ]
    return {
        "planList": items,
        "loop": cc.loop,
        "skipPlan": cc.skip_plan,
        "useCoupon": cc.use_coupon,
        "restoreCharge": cc.restore_charge,
    }


@router.get("/charge-plan/options")
def get_charge_plan_options(category: str | None = None, missionType: str | None = None):
    """获取体力计划下拉选项。可按需传 category / missionType 以过滤后两级。
    - category 为空时返回全部分类列表
    - missionType 依赖 category
    """
    ctx = get_ctx()
    comp = ctx.compendium_service
    from zzz_od.application.charge_plan.charge_plan_config import CardNumEnum
    from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntBuffEnum

    category_list = [ {"label": c.label, "value": c.value} for c in comp.get_charge_plan_category_list() ]

    mission_type_list = []
    if category:
        mission_type_list = [ {"label": c.label, "value": c.value} for c in comp.get_charge_plan_mission_type_list(category) ]

    mission_list = []
    if category and missionType:
        mission_list = [ {"label": c.label, "value": c.value} for c in comp.get_charge_plan_mission_list(category, missionType) ]

    card_num_list = [ {"label": e.value.label, "value": e.value.value} for e in CardNumEnum ]
    notorious_buff_list = [ {"label": str(e.value.value), "value": e.value.value} for e in NotoriousHuntBuffEnum ]

    # 队伍 & 自动战斗配置
    team_list = [ {"label": "游戏内配队", "value": -1} ]
    for t in ctx.team_config.team_list:
        team_list.append({"label": t.name, "value": t.idx})
    from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list
    auto_battle_list = [ {"label": c.label, "value": c.value} for c in get_auto_battle_op_config_list(sub_dir='auto_battle') ]

    return {
        "categoryList": category_list,
        "missionTypeList": mission_type_list,
        "missionList": mission_list,
        "cardNumList": card_num_list,
        "notoriousHuntBuffList": notorious_buff_list,
        "teamList": team_list,
        "autoBattleList": auto_battle_list,
    }


@router.put("/charge-plan")
def update_charge_plan(payload: dict):
    ctx = get_ctx()
    cc = ctx.charge_plan_config
    if "loop" in payload:
        cc.loop = bool(payload["loop"])
    if "skipPlan" in payload:
        cc.skip_plan = bool(payload["skipPlan"])
    if "useCoupon" in payload:
        cc.use_coupon = bool(payload["useCoupon"])
    if "restoreCharge" in payload:
        cc.restore_charge = payload["restoreCharge"]
    return {"ok": True}


# -------- 咖啡计划 --------


@router.get("/coffee-plan")
def get_coffee_plan():
    ctx = get_ctx()
    c: CoffeeConfig = ctx.coffee_config
    return {
        "chooseWay": c.choose_way,  # 选择方式（优先体力计划/汀曼特调）
        "challengeWay": c.challenge_way,  # 挑战方式（全都/只计划/不挑战）
        "cardNum": c.card_num,  # 卡片数量（默认/1）
        "autoBattle": c.auto_battle,
        "day": {
            1: c.day_coffee_1,
            2: c.day_coffee_2,
            3: c.day_coffee_3,
            4: c.day_coffee_4,
            5: c.day_coffee_5,
            6: c.day_coffee_6,
            7: c.day_coffee_7,
        },
        "predefinedTeamIdx": c.predefined_team_idx,
        "runChargePlanAfterwards": c.run_charge_plan_afterwards,
    }


@router.put("/coffee-plan")
def update_coffee_plan(payload: dict):
    ctx = get_ctx()
    c: CoffeeConfig = ctx.coffee_config
    if "chooseWay" in payload:
        c.choose_way = payload["chooseWay"]
    if "challengeWay" in payload:
        c.challenge_way = payload["challengeWay"]
    if "cardNum" in payload:
        c.card_num = payload["cardNum"]
    if "autoBattle" in payload:
        c.auto_battle = payload["autoBattle"]
    day = payload.get("day") or {}
    if 1 in day:
        c.day_coffee_1 = day[1]
    if 2 in day:
        c.day_coffee_2 = day[2]
    if 3 in day:
        c.day_coffee_3 = day[3]
    if 4 in day:
        c.day_coffee_4 = day[4]
    if 5 in day:
        c.day_coffee_5 = day[5]
    if 6 in day:
        c.day_coffee_6 = day[6]
    if 7 in day:
        c.day_coffee_7 = day[7]
    if "predefinedTeamIdx" in payload:
        c.predefined_team_idx = int(payload["predefinedTeamIdx"])
    if "runChargePlanAfterwards" in payload:
        c.run_charge_plan_afterwards = bool(payload["runChargePlanAfterwards"])
    return {"ok": True}


# -------- 式舆防卫战 --------


@router.get("/shiyu-defense")
def get_shiyu_defense():
    ctx = get_ctx()
    s: ShiyuDefenseConfig = ctx.shiyu_defense_config
    return {
        "criticalMaxNodeIdx": s.critical_max_node_idx,
        "teams": [
            {
                "teamIdx": t.team_idx,
                "forCritical": t.for_critical,
                "weaknessList": [d.name for d in t.weakness_list],
            }
            for t in s.team_list
        ],
    }


@router.put("/shiyu-defense")
def update_shiyu_defense(payload: dict):
    ctx = get_ctx()
    s: ShiyuDefenseConfig = ctx.shiyu_defense_config
    if "criticalMaxNodeIdx" in payload:
        s.critical_max_node_idx = int(payload["criticalMaxNodeIdx"])
    teams = payload.get("teams") or []
    # 重建 team_list（按传入覆盖）
    s.team_list.clear()
    for t in teams:
        team_idx = int(t.get("teamIdx", -1))
        for_critical = bool(t.get("forCritical", False))
        weakness_names = t.get("weaknessList", []) or []
        weakness_list = [DmgTypeEnum.from_name(n) for n in weakness_names]
        s.team_list.append(
            s.get_config_by_team_idx(team_idx)
        )
        conf = s.get_config_by_team_idx(team_idx)
        conf.for_critical = for_critical
        conf.weakness_list = weakness_list
    s.save_team_list()
    return {"ok": True}


@router.post("/charge-plan")
def add_charge_plan(payload: dict):
    ctx = get_ctx()
    cc = ctx.charge_plan_config
    cc.add_plan({
        'tab_name': payload.get('tabName', '训练'),
        'category_name': payload.get('categoryName', '实战模拟室'),
        'mission_type_name': payload.get('missionTypeName', '基础材料'),
        'mission_name': payload.get('missionName', '调查专项'),
        'level': payload.get('level', '默认等级'),
        'auto_battle_config': payload.get('autoBattleConfig', '全配队通用'),
        'run_times': payload.get('runTimes', 0),
        'plan_times': payload.get('planTimes', 1),
        'card_num': payload.get('cardNum'),
        'predefined_team_idx': payload.get('predefinedTeamIdx', -1),
        'notorious_hunt_buff_num': payload.get('notoriousHuntBuffNum', 1),
    })
    return {"ok": True}


@router.put("/charge-plan/{idx}")
def update_charge_plan_item(idx: int, payload: dict):
    ctx = get_ctx()
    cc = ctx.charge_plan_config
    plan = ChargePlanItem(
        tab_name=payload.get('tabName', '训练'),
        category_name=payload.get('categoryName', '实战模拟室'),
        mission_type_name=payload.get('missionTypeName', '基础材料'),
        mission_name=payload.get('missionName', '调查专项'),
        level=payload.get('level', '默认等级'),
        auto_battle_config=payload.get('autoBattleConfig', '全配队通用'),
        run_times=payload.get('runTimes', 0),
        plan_times=payload.get('planTimes', 1),
    card_num=str(payload.get('cardNum')) if payload.get('cardNum') is not None else '默认数量',
        predefined_team_idx=payload.get('predefinedTeamIdx', -1),
        notorious_hunt_buff_num=payload.get('notoriousHuntBuffNum', 1),
        plan_id=payload.get('planId'),
    )
    cc.update_plan(idx, plan)
    return {"ok": True}


@router.delete("/charge-plan/{idx}")
def delete_charge_plan_item(idx: int):
    ctx = get_ctx()
    ctx.charge_plan_config.delete_plan(idx)
    return {"ok": True}


@router.post("/charge-plan:reorder")
def reorder_charge_plan(payload: dict):
    """
    重排体力计划。
    - mode="move_up" 时，仅使用 from 作为 idx，调用 move_up(idx)
    - mode="move_top" 时，仅使用 from 作为 idx，调用 move_top(idx)
    其余模式暂不支持。
    """
    ctx = get_ctx()
    cc = ctx.charge_plan_config
    mode = (payload.get("mode") or "").lower()
    try:
        _from_val = payload.get("from")
        frm = int(_from_val) if _from_val is not None else -1
    except Exception:
        frm = -1
    if mode == "move_up" and frm >= 0:
        cc.move_up(frm)
        return {"ok": True}
    if mode == "move_top" and frm >= 0:
        cc.move_top(frm)
        return {"ok": True}
    return {"ok": False, "error": {"code": "UNSUPPORTED_MODE", "message": mode}}


@router.post("/charge-plan:clear-completed")
def clear_completed_charge_plan():
    ctx = get_ctx()
    cc = ctx.charge_plan_config
    not_completed = [p for p in cc.plan_list if p.run_times < p.plan_times]
    cc.plan_list = not_completed
    cc.save()
    return {"ok": True}


@router.post("/charge-plan:clear-all")
def clear_all_charge_plan():
    """删除所有体力计划（对应 PySide '删除所有' 按钮）。"""
    ctx = get_ctx()
    cc = ctx.charge_plan_config
    cc.plan_list.clear()
    cc.save()
    return {"ok": True}


# -------- Notorious Hunt (恶名狩猎) --------


@router.get("/notorious-hunt/options")
def get_notorious_hunt_options():
    """获取恶名狩猎的下拉框选项"""
    from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntLevelEnum, NotoriousHuntBuffEnum
    from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list

    ctx = get_ctx()

    # 获取任务类型选项
    mission_type_options = []
    try:
        config_list = ctx.compendium_service.get_charge_plan_mission_type_list('恶名狩猎')
        mission_type_options = [{'label': c.label, 'value': c.value} for c in config_list]
    except:
        # 如果服务不可用，使用默认选项
        default_mission_types = [
            '初生死路屠夫', '未知复合侵蚀体', '冥宁芙·双子',
            '「霸主侵蚀体·庞培」', '牲鬼·布林格', '秽息司祭'
        ]
        mission_type_options = [{'label': m, 'value': m} for m in default_mission_types]

    # 获取等级选项
    level_options = [{'label': level.value.value, 'value': level.value.value} for level in NotoriousHuntLevelEnum]

    # 获取Buff选项
    buff_options = [{'label': buff.value.label, 'value': buff.value.value} for buff in NotoriousHuntBuffEnum]

    # 获取自动战斗配置选项
    try:
        config_list = get_auto_battle_op_config_list('auto_battle')
        auto_battle_options = [{'label': c.label, 'value': c.value} for c in config_list]
        if not auto_battle_options:
            auto_battle_options = [{'label': '全配队通用', 'value': '全配队通用'}]
    except Exception:
        auto_battle_options = [{'label': '全配队通用', 'value': '全配队通用'}]

    return {
        "missionTypes": mission_type_options,
        "levels": level_options,
        "buffs": buff_options,
        "autoBattleConfigs": auto_battle_options
    }


@router.get("/notorious-hunt")
def get_notorious_hunt():
    ctx = get_ctx()
    nh: NotoriousHuntConfig = ctx.notorious_hunt_config
    items = [
        {
            "tabName": p.tab_name,
            "categoryName": p.category_name,
            "missionTypeName": p.mission_type_name,
            "missionName": p.mission_name,
            "level": p.level,
            "predefinedTeamIdx": p.predefined_team_idx,
            "autoBattleConfig": p.auto_battle_config,
            "runTimes": p.run_times,
            "planTimes": p.plan_times,
            "notoriousHuntBuffNum": p.notorious_hunt_buff_num,
        }
        for p in nh.plan_list
    ]
    return {"planList": items}


@router.put("/notorious-hunt")
def update_notorious_hunt(payload: dict):
    ctx = get_ctx()
    nh: NotoriousHuntConfig = ctx.notorious_hunt_config
    items = payload.get("planList") or []
    for i, item in enumerate(items):
        plan = ChargePlanItem(
            tab_name=item.get('tabName', '作战'),
            category_name=item.get('categoryName', '恶名狩猎'),
            mission_type_name=item.get('missionTypeName', None),
            mission_name=item.get('missionName', None),
            level=item.get('level', '默认等级'),
            auto_battle_config=item.get('autoBattleConfig'),
            run_times=item.get('runTimes', 0),
            plan_times=item.get('planTimes', 1),
            predefined_team_idx=item.get('predefinedTeamIdx', -1),
            notorious_hunt_buff_num=item.get('notoriousHuntBuffNum', 1),
        )
        nh.update_plan(i, plan)
    return {"ok": True}


@router.get("/run/{run_id}/status", response_model=RunStatusResponse)
async def onedragon_status(run_id: str) -> RunStatusResponse:
    ctx = get_ctx()
    # augment status with aggregate progress info
    agg = build_onedragon_aggregate(ctx)
    message = f"{ctx.context_running_status_text} ({int(agg['progress']*100)}%)"
    status = _registry.get_status(run_id, message=message)
    if status is None:
        return RunStatusResponse(runId=run_id, status=RunStatusEnum.FAILED, message="Run not found", progress=0.0)
    return status


# -------- Team config --------


@router.get("/team")
def get_team():
    from zzz_od.game_data.agent import AgentEnum

    def agent_id_to_name(agent_id: str) -> str:
        if agent_id == 'unknown':
            return '未知'
        for agent_enum in AgentEnum:
            if agent_enum.value.agent_id == agent_id:
                return agent_enum.value.agent_name
        return agent_id

    ctx = get_ctx()
    tc = ctx.team_config
    teams = [
        {
            "idx": t.idx,
            "name": t.name,
            "members": [
                {
                    "agentId": agent_id,
                    "name": agent_id_to_name(agent_id)
                }
                for agent_id in t.agent_id_list
            ],
            "autoBattle": t.auto_battle,
        }
        for t in tc.team_list
    ]
    return {"teams": teams}


@router.get("/apps")
def get_apps():
    """
    返回一条龙可运行的应用清单（按当前顺序与启停）。
    - items: [{ appId, name, enabled, orderIndex }]
    - 兼容：附带 appOrder / appRunList 便于前端调试或迁移
    """
    ctx = get_ctx()
    items = []
    try:
        # 复用统一的目录构建（同模块函数）
        items = _get_app_catalog()
    except Exception:
        # 兜底：最小化返回
        try:
            from zzz_od.application.zzz_one_dragon_app import ZOneDragonApp
            zapp = ZOneDragonApp(ctx)
            run_set = set(ctx.one_dragon_app_config.app_run_list)
            for idx, app in enumerate(zapp.get_one_dragon_apps_in_order()):
                app_id = getattr(app, 'app_id', '')
                app_name = getattr(app, 'op_name', app_id)
                items.append({
                    'appId': app_id,
                    'name': app_name,
                    'enabled': app_id in run_set,
                    'orderIndex': idx,
                })
        except Exception:
            pass
    odc = ctx.one_dragon_app_config
    return {
        'items': items,
        'appOrder': odc.app_order,
        'appRunList': odc.app_run_list,
    }


@router.put("/apps")
def update_apps(payload: dict):
    """
    更新应用顺序与运行列表。
    - appOrder: 完整顺序数组（可选）
    - appRunList: 需要在一条龙中运行的 app_id 列表（可选）
    """
    ctx = get_ctx()
    # 写入 OneDragonAppConfig
    odc = ctx.one_dragon_app_config
    items = payload.get("items")
    if isinstance(items, list) and items:
        # 由 items 推导顺序与启停
        try:
            sorted_items = sorted(items, key=lambda x: int(x.get("orderIndex", 0)))
        except Exception:
            sorted_items = items
        new_order = [i.get("appId") for i in sorted_items if isinstance(i.get("appId"), str)]
        new_run_list = [i.get("appId") for i in sorted_items if i.get("enabled") and isinstance(i.get("appId"), str)]
        odc.app_order = new_order
        odc.app_run_list = new_run_list
    else:
        if "appOrder" in payload and isinstance(payload["appOrder"], list):
            odc.app_order = payload["appOrder"]
        if "appRunList" in payload and isinstance(payload["appRunList"], list):
            odc.app_run_list = payload["appRunList"]
    return {"ok": True}


# -------- 单项执行（按模块运行）--------


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


def _run_via_onedragon_with_temp(app_ids: list[str]) -> str:
    """通过一条龙总控运行指定 appId 列表（临时运行清单）。"""
    ctx = get_ctx()
    original_temp = getattr(ctx.one_dragon_app_config, "_temp_app_run_list", None)
    ctx.one_dragon_app_config.set_temp_app_run_list(app_ids)
    from zzz_od.application.zzz_one_dragon_app import ZOneDragonApp
    run_id = _start_app_run(lambda c: ZOneDragonApp(c))
    # 由 after_app_shutdown 自动清理 temp；若需要也可在桥接 detach 里兜底
    return run_id


@router.post("/charge-plan/run")
async def run_charge_plan():
    run_id = _run_via_onedragon_with_temp(["charge_plan"])  # app_id 按实际定义
    return {"runId": run_id}


@router.post("/notorious-hunt/run")
async def run_notorious_hunt():
    run_id = _run_via_onedragon_with_temp(["notorious_hunt"])  # 以 GUI 内部 app_id 为准
    return {"runId": run_id}


@router.post("/coffee-plan/run")
async def run_coffee_plan():
    run_id = _run_via_onedragon_with_temp(["coffee"])  # 以 GUI 内部 app_id 为准
    return {"runId": run_id}


@router.post("/shiyu-defense/run")
async def run_shiyu_defense():
    run_id = _run_via_onedragon_with_temp(["shiyu_defense"])  # 以 GUI 内部 app_id 为准
    return {"runId": run_id}


# 可选：通用按 appId 运行（前端可直接调用）
@router.post("/apps/{appId}:run")
async def run_app_by_id(appId: str):
    # 统一通过一条龙运行，确保进/出游戏与实例切换等流程完整
    run_id = _run_via_onedragon_with_temp([appId])
    return {"runId": run_id}


# 兼容路由：/apps/{appId}/run 与 /run-app/{appId}
@router.post("/apps/{appId}/run")
async def run_app_alias_path(appId: str):
    return await run_app_by_id(appId)


@router.post("/run-app/{appId}")
async def run_app_alias_legacy(appId: str):
    return await run_app_by_id(appId)


@router.put("/team")
def update_team(payload: dict):
    ctx = get_ctx()
    tc = ctx.team_config
    items = payload.get("teams") or []
    for item in items:
        idx = int(item.get("idx", -1))
        name = item.get("name") or f"编队{idx+1}"
        members = item.get("members") or []
        auto_battle = item.get("autoBattle") or "全配队通用"
        t = PredefinedTeamInfo(idx=idx, name=name, auto_battle=auto_battle, agent_id_list=members)
        tc.update_team(t)
    return {"ok": True}


# -------- OneDragon apps (list, toggle, reorder, single-run) --------


def _get_app_catalog() -> List[dict]:
    ctx = get_ctx()
    run_set = set(ctx.one_dragon_app_config.app_run_list)
    from zzz_od.application.zzz_one_dragon_app import ZOneDragonApp

    app = ZOneDragonApp(ctx)
    apps = app.get_one_dragon_apps_in_order()
    items: List[dict] = []
    for idx, a in enumerate(apps):
        items.append({
            "appId": getattr(a, "app_id", f"app-{idx}"),
            "name": getattr(a, "op_name", getattr(a, "app_id", f"app-{idx}")),
            "enabled": getattr(a, "app_id", None) in run_set,
            "orderIndex": idx,
        })
    return items


## 注意：为避免与上面的 get_apps 重复注册，这里移除重复的 GET /apps 定义


@router.put("/apps/{app_id}")
def set_onedragon_app_enabled(app_id: str, payload: dict):
    ctx = get_ctx()
    to_run = bool(payload.get("toRun", True))
    ctx.one_dragon_app_config.set_app_run(app_id, to_run)
    return {"ok": True}


@router.post("/apps:reorder")
def reorder_onedragon_apps(payload: dict):
    """
    Reorder apps.
    - mode: "move_up" | "move_top"
    - appId: target app id
    """
    ctx = get_ctx()
    mode = (payload.get("mode") or "").lower()
    app_id = payload.get("appId")
    if not app_id:
        return {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "appId required"}}

    if mode == "move_up":
        ctx.one_dragon_app_config.move_up_app(app_id)
        return {"ok": True}
    if mode == "move_top":
        orders: List[str] = list(ctx.one_dragon_app_config.app_order)
        if app_id in orders:
            orders.remove(app_id)
            orders.insert(0, app_id)
            ctx.one_dragon_app_config.app_order = orders
        return {"ok": True}
    return {"ok": False, "error": {"code": "UNSUPPORTED_MODE", "message": mode}}


@router.post("/run-app/{app_id}")
def run_single_app(app_id: str):
    """Run only a single OneDragon sub-app by app_id."""
    ctx = get_ctx()

    def _factory() -> asyncio.Task:
        async def runner():
            loop = asyncio.get_running_loop()

            def _exec():
                original_temp = ctx.one_dragon_app_config._temp_app_run_list
                try:
                    ctx.one_dragon_app_config.set_temp_app_run_list([app_id])
                    from zzz_od.application.zzz_one_dragon_app import ZOneDragonApp
                    ZOneDragonApp(ctx).execute()
                finally:
                    ctx.one_dragon_app_config.clear_temp_app_run_list()
                    if original_temp is not None:
                        ctx.one_dragon_app_config.set_temp_app_run_list(original_temp)

            await loop.run_in_executor(None, _exec)

        return asyncio.create_task(runner())

    run_id = _registry.create(_factory)
    attach_run_event_bridge(ctx, run_id)
    return RunIdResponse(runId=run_id)


