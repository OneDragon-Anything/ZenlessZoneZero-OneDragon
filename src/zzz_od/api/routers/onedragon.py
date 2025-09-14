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
from zzz_od.game_data.agent import DmgTypeEnum, AgentEnum
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.bridges import attach_run_event_bridge


router = APIRouter(
    prefix="/api/v1/onedragon",
    tags=["一条龙 OneDragon"],
    dependencies=[Depends(get_api_key_dependency())],
)


_registry = get_global_run_registry()


@router.post("/run", response_model=RunIdResponse, summary="启动一条龙自动化任务")
async def onedragon_run() -> RunIdResponse:
    """
    启动一条龙自动化任务

    ## 功能描述
    启动一条龙总控程序，按照配置的计划自动执行各种游戏任务，包括体力消耗、日常任务等。

    ## 返回数据
    - **runId**: 任务运行ID，用于后续状态查询和控制

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **CONFIG_ERROR**: 配置错误
    - **PLAN_EMPTY**: 计划列表为空

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/run")
    task_info = response.json()
    print(f"一条龙任务ID: {task_info['runId']}")
    ```
    """
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


@router.post("/run/{run_id}:cancel", summary="取消一条龙任务")
async def onedragon_cancel(run_id: str):
    """
    取消指定的一条龙任务

    ## 功能描述
    取消正在运行的一条龙任务，停止所有相关的自动化操作。

    ## 路径参数
    - **run_id**: 要取消的任务运行ID

    ## 返回数据
    - **ok**: 操作是否成功

    ## 错误码
    - **TASK_NOT_FOUND**: 任务不存在
    - **TASK_CANCEL_FAILED**: 任务取消失败

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/run/task123:cancel")
    result = response.json()
    print(f"取消结果: {result['ok']}")
    ```
    """
    _registry.cancel(run_id)
    ctx = get_ctx()
    ctx.stop_running()
    return {"ok": True}


# -------- Charge plan --------
@router.get("/charge-plan", summary="获取体力计划配置")
def get_charge_plan():
    """
    获取当前的体力计划配置

    ## 功能描述
    返回完整的体力计划配置，包括计划列表和全局设置。

    ## 返回数据
    - **planList**: 计划项目列表
      - **tabName**: 标签页名称
      - **categoryName**: 分类名称
      - **missionTypeName**: 任务类型名称
      - **missionName**: 任务名称
      - **level**: 关卡等级
      - **autoBattleConfig**: 自动战斗配置
      - **runTimes**: 已运行次数
      - **planTimes**: 计划次数
      - **cardNum**: 卡片数量
      - **predefinedTeamIdx**: 预设队伍索引
      - **notoriousHuntBuffNum**: 恶名狩猎增益数量
      - **planId**: 计划ID
    - **loop**: 是否循环执行
    - **skipPlan**: 是否跳过计划
    - **useCoupon**: 是否使用优惠券
    - **restoreCharge**: 是否恢复体力

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/onedragon/charge-plan")
    plan = response.json()
    print(f"计划数量: {len(plan['planList'])}")
    ```
    """
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


@router.get("/charge-plan/options", summary="获取体力计划配置选项")
def get_charge_plan_options(category: str | None = None, missionType: str | None = None):
    """
    获取体力计划的所有配置选项

    ## 功能描述
    返回体力计划配置所需的所有下拉选项，包括分类、任务类型、任务列表、队伍配置等。

    ## 查询参数
    - **category** (可选): 分类名称，用于过滤任务类型
    - **missionType** (可选): 任务类型名称，用于过滤具体任务

    ## 返回数据
    - **categoryList**: 分类选项列表
    - **missionTypeList**: 任务类型选项列表（根据category过滤）
    - **missionList**: 任务选项列表（根据category和missionType过滤）
    - **cardNumList**: 卡片数量选项
    - **notoriousHuntBuffList**: 恶名狩猎增益选项
    - **teamList**: 队伍配置选项
    - **autoBattleList**: 自动战斗配置选项

    ## 使用示例
    ```python
    import requests
    # 获取所有分类
    response = requests.get("http://localhost:8000/api/v1/onedragon/charge-plan/options")
    options = response.json()

    # 获取特定分类的任务类型
    response = requests.get("http://localhost:8000/api/v1/onedragon/charge-plan/options?category=训练")
    ```
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


@router.put("/charge-plan", summary="更新体力计划全局设置")
def update_charge_plan(payload: dict):
    """
    更新体力计划的全局配置设置

    ## 功能描述
    更新体力计划的全局开关和设置，如循环执行、跳过计划、使用优惠券等。

    ## 请求参数
    - **loop** (可选): 是否循环执行，布尔值
    - **skipPlan** (可选): 是否跳过计划，布尔值
    - **useCoupon** (可选): 是否使用优惠券，布尔值
    - **restoreCharge** (可选): 恢复体力设置

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "loop": True,
        "useCoupon": False,
        "restoreCharge": "不恢复"
    }
    response = requests.put("http://localhost:8000/api/v1/onedragon/charge-plan", json=data)
    ```
    """
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


@router.get("/coffee-plan", summary="获取咖啡计划配置")
def get_coffee_plan():
    """
    获取咖啡计划的配置信息

    ## 功能描述
    返回咖啡计划的详细配置，包括选择方式、挑战方式、每日咖啡配置等。

    ## 返回数据
    - **chooseWay**: 选择方式（优先体力计划/汀曼特调）
    - **challengeWay**: 挑战方式（全都/只计划/不挑战）
    - **cardNum**: 卡片数量设置
    - **autoBattle**: 自动战斗配置
    - **day**: 每日咖啡配置（1-7对应周一到周日）
    - **predefinedTeamIdx**: 预设队伍索引
    - **runChargePlanAfterwards**: 是否在咖啡计划后运行体力计划

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/onedragon/coffee-plan")
    config = response.json()
    print(f"选择方式: {config['chooseWay']}")
    ```
    """
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


@router.put("/coffee-plan", summary="更新咖啡计划配置")
def update_coffee_plan(payload: dict):
    """
    更新咖啡计划的配置设置

    ## 功能描述
    更新咖啡计划的各项配置，包括选择方式、挑战方式、每日咖啡设置等。

    ## 请求参数
    - **chooseWay** (可选): 选择方式
    - **challengeWay** (可选): 挑战方式
    - **cardNum** (可选): 卡片数量
    - **autoBattle** (可选): 自动战斗配置
    - **day** (可选): 每日咖啡配置对象，键为1-7（周一到周日）
    - **predefinedTeamIdx** (可选): 预设队伍索引
    - **runChargePlanAfterwards** (可选): 是否在咖啡计划后运行体力计划

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "chooseWay": "优先体力计划",
        "day": {
            "1": "咖啡配置1",
            "2": "咖啡配置2"
        }
    }
    response = requests.put("http://localhost:8000/api/v1/onedragon/coffee-plan", json=data)
    ```
    """
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


@router.get("/shiyu-defense", summary="获取式舆防卫战配置")
def get_shiyu_defense():
    """
    获取式舆防卫战的配置信息

    ## 功能描述
    返回式舆防卫战的队伍配置和关卡设置。

    ## 返回数据
    - **criticalMaxNodeIdx**: 危险关卡最大节点索引
    - **teams**: 队伍配置列表
      - **teamIdx**: 队伍索引
      - **forCritical**: 是否用于危险关卡
      - **weaknessList**: 弱点属性列表

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/onedragon/shiyu-defense")
    config = response.json()
    print(f"危险关卡节点: {config['criticalMaxNodeIdx']}")
    ```
    """
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


@router.put("/shiyu-defense", summary="更新式舆防卫战配置")
def update_shiyu_defense(payload: dict):
    """
    更新式舆防卫战的配置设置

    ## 功能描述
    更新式舆防卫战的队伍配置和关卡设置。

    ## 请求参数
    - **criticalMaxNodeIdx** (可选): 危险关卡最大节点索引
    - **teams** (可选): 队伍配置列表
      - **teamIdx**: 队伍索引
      - **forCritical**: 是否用于危险关卡
      - **weaknessList**: 弱点属性名称列表

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "criticalMaxNodeIdx": 5,
        "teams": [
            {
                "teamIdx": 1,
                "forCritical": True,
                "weaknessList": ["物理", "火"]
            }
        ]
    }
    response = requests.put("http://localhost:8000/api/v1/onedragon/shiyu-defense", json=data)
    ```
    """
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


@router.post("/charge-plan", summary="添加体力计划项目")
def add_charge_plan(payload: dict):
    """
    添加新的体力计划项目

    ## 功能描述
    向体力计划列表中添加一个新的计划项目。

    ## 请求参数
    - **tabName** (可选): 标签页名称，默认"训练"
    - **categoryName** (可选): 分类名称，默认"实战模拟室"
    - **missionTypeName** (可选): 任务类型名称，默认"基础材料"
    - **missionName** (可选): 任务名称，默认"调查专项"
    - **level** (可选): 关卡等级，默认"默认等级"
    - **autoBattleConfig** (可选): 自动战斗配置，默认"全配队通用"
    - **runTimes** (可选): 已运行次数，默认0
    - **planTimes** (可选): 计划次数，默认1
    - **cardNum** (可选): 卡片数量
    - **predefinedTeamIdx** (可选): 预设队伍索引，默认-1
    - **notoriousHuntBuffNum** (可选): 恶名狩猎增益数量，默认1

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "missionName": "新任务",
        "planTimes": 5,
        "predefinedTeamIdx": 1
    }
    response = requests.post("http://localhost:8000/api/v1/onedragon/charge-plan", json=data)
    ```
    """
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


@router.put("/charge-plan/{idx}", summary="更新体力计划项目")
def update_charge_plan_item(idx: int, payload: dict):
    """
    更新指定索引的体力计划项目

    ## 功能描述
    根据索引更新体力计划列表中的特定项目配置。

    ## 路径参数
    - **idx**: 计划项目的索引位置

    ## 请求参数
    - **tabName** (可选): 标签页名称
    - **categoryName** (可选): 分类名称
    - **missionTypeName** (可选): 任务类型名称
    - **missionName** (可选): 任务名称
    - **level** (可选): 关卡等级
    - **autoBattleConfig** (可选): 自动战斗配置
    - **runTimes** (可选): 已运行次数
    - **planTimes** (可选): 计划次数
    - **cardNum** (可选): 卡片数量
    - **predefinedTeamIdx** (可选): 预设队伍索引
    - **notoriousHuntBuffNum** (可选): 恶名狩猎增益数量
    - **planId** (可选): 计划ID

    ## 返回数据
    - **ok**: 操作是否成功

    ## 错误码
    - **INVALID_INDEX**: 索引无效
    - **UPDATE_FAILED**: 更新失败

    ## 使用示例
    ```python
    import requests
    data = {
        "planTimes": 10,
        "autoBattleConfig": "新配置"
    }
    response = requests.put("http://localhost:8000/api/v1/onedragon/charge-plan/0", json=data)
    ```
    """
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


@router.delete("/charge-plan/{idx}", summary="删除体力计划项目")
def delete_charge_plan_item(idx: int):
    """
    删除指定索引的体力计划项目

    ## 功能描述
    从体力计划列表中删除指定索引位置的计划项目。

    ## 路径参数
    - **idx**: 要删除的计划项目索引

    ## 返回数据
    - **ok**: 操作是否成功

    ## 错误码
    - **INVALID_INDEX**: 索引无效
    - **DELETE_FAILED**: 删除失败

    ## 使用示例
    ```python
    import requests
    response = requests.delete("http://localhost:8000/api/v1/onedragon/charge-plan/0")
    result = response.json()
    print(f"删除结果: {result['ok']}")
    ```
    """
    ctx = get_ctx()
    ctx.charge_plan_config.delete_plan(idx)
    return {"ok": True}


@router.post("/charge-plan:reorder", summary="重新排序体力计划")
def reorder_charge_plan(payload: dict):
    """
    重新排序体力计划项目

    ## 功能描述
    调整体力计划列表中项目的顺序，支持上移和置顶操作。

    ## 请求参数
    - **mode**: 操作模式
      - "move_up": 上移一位
      - "move_top": 移动到顶部
    - **from**: 要移动的项目索引

    ## 返回数据
    - **ok**: 操作是否成功
    - **error** (失败时): 错误信息
      - **code**: 错误代码
      - **message**: 错误消息

    ## 错误码
    - **UNSUPPORTED_MODE**: 不支持的操作模式
    - **INVALID_INDEX**: 索引无效

    ## 使用示例
    ```python
    import requests
    # 将索引2的项目上移一位
    data = {"mode": "move_up", "from": 2}
    response = requests.post("http://localhost:8000/api/v1/onedragon/charge-plan:reorder", json=data)

    # 将索引1的项目移到顶部
    data = {"mode": "move_top", "from": 1}
    response = requests.post("http://localhost:8000/api/v1/onedragon/charge-plan:reorder", json=data)
    ```
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


@router.post("/charge-plan:clear-completed", summary="清除已完成的体力计划")
def clear_completed_charge_plan():
    """
    清除所有已完成的体力计划项目

    ## 功能描述
    删除体力计划列表中所有已完成的项目（运行次数达到计划次数的项目）。

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/charge-plan:clear-completed")
    result = response.json()
    print(f"清除结果: {result['ok']}")
    ```
    """
    ctx = get_ctx()
    cc = ctx.charge_plan_config
    not_completed = [p for p in cc.plan_list if p.run_times < p.plan_times]
    cc.plan_list = not_completed
    cc.save()
    return {"ok": True}


@router.post("/charge-plan:clear-all", summary="清除所有体力计划")
def clear_all_charge_plan():
    """
    清除所有体力计划项目

    ## 功能描述
    删除体力计划列表中的所有项目，清空整个计划列表。

    ## 返回数据
    - **ok**: 操作是否成功

    ## 注意事项
    - 此操作不可逆，请谨慎使用
    - 建议在执行前确认用户意图

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/charge-plan:clear-all")
    result = response.json()
    print(f"清空结果: {result['ok']}")
    ```
    """
    ctx = get_ctx()
    cc = ctx.charge_plan_config
    cc.plan_list.clear()
    cc.save()
    return {"ok": True}


# -------- Notorious Hunt (恶名狩猎) --------


@router.get("/notorious-hunt/options", summary="获取恶名狩猎配置选项")
def get_notorious_hunt_options():
    """
    获取恶名狩猎的所有配置选项

    ## 功能描述
    返回恶名狩猎配置所需的所有下拉选项，包括任务类型、等级、增益和自动战斗配置。

    ## 返回数据
    - **missionTypes**: 任务类型选项列表
      - **label**: 显示名称
      - **value**: 选项值
    - **levels**: 等级选项列表
    - **buffs**: 增益选项列表
    - **autoBattleConfigs**: 自动战斗配置选项列表

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/onedragon/notorious-hunt/options")
    options = response.json()
    print(f"可用任务类型: {[m['label'] for m in options['missionTypes']]}")
    ```
    """
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


@router.get("/notorious-hunt", summary="获取恶名狩猎配置")
def get_notorious_hunt():
    """
    获取恶名狩猎的计划配置

    ## 功能描述
    返回恶名狩猎的详细计划配置列表。

    ## 返回数据
    - **planList**: 恶名狩猎计划列表
      - **tabName**: 标签页名称
      - **categoryName**: 分类名称
      - **missionTypeName**: 任务类型名称
      - **missionName**: 任务名称
      - **level**: 关卡等级
      - **predefinedTeamIdx**: 预设队伍索引
      - **autoBattleConfig**: 自动战斗配置
      - **runTimes**: 已运行次数
      - **planTimes**: 计划次数
      - **notoriousHuntBuffNum**: 恶名狩猎增益数量

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/onedragon/notorious-hunt")
    config = response.json()
    print(f"恶名狩猎计划数量: {len(config['planList'])}")
    ```
    """
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


@router.put("/notorious-hunt", summary="更新恶名狩猎配置")
def update_notorious_hunt(payload: dict):
    """
    更新恶名狩猎的计划配置

    ## 功能描述
    批量更新恶名狩猎的计划列表配置。

    ## 请求参数
    - **planList**: 恶名狩猎计划列表
      - **tabName** (可选): 标签页名称，默认"作战"
      - **categoryName** (可选): 分类名称，默认"恶名狩猎"
      - **missionTypeName**: 任务类型名称
      - **missionName**: 任务名称
      - **level** (可选): 关卡等级，默认"默认等级"
      - **autoBattleConfig**: 自动战斗配置
      - **runTimes** (可选): 已运行次数，默认0
      - **planTimes** (可选): 计划次数，默认1
      - **predefinedTeamIdx** (可选): 预设队伍索引，默认-1
      - **notoriousHuntBuffNum** (可选): 恶名狩猎增益数量，默认1

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "planList": [
            {
                "missionTypeName": "初生死路屠夫",
                "missionName": "初生死路屠夫",
                "autoBattleConfig": "全配队通用",
                "planTimes": 3
            }
        ]
    }
    response = requests.put("http://localhost:8000/api/v1/onedragon/notorious-hunt", json=data)
    ```
    """
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


@router.get("/run/{run_id}/status", response_model=RunStatusResponse, summary="获取一条龙任务状态")
async def onedragon_status(run_id: str) -> RunStatusResponse:
    """
    获取指定一条龙任务的运行状态

    ## 功能描述
    查询指定任务ID的一条龙任务运行状态，包括进度信息和当前状态。

    ## 路径参数
    - **run_id**: 任务运行ID

    ## 返回数据
    - **runId**: 任务运行ID
    - **status**: 任务状态（pending/running/completed/failed/cancelled）
    - **message**: 状态消息，包含进度百分比
    - **progress**: 任务进度（0.0-1.0）

    ## 错误码
    - **TASK_NOT_FOUND**: 任务不存在

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/onedragon/run/task123/status")
    status = response.json()
    print(f"任务状态: {status['status']}, 进度: {status['progress']*100}%")
    ```
    """
    ctx = get_ctx()
    # augment status with aggregate progress info
    agg = build_onedragon_aggregate(ctx)
    message = f"{ctx.context_running_status_text} ({int(agg['progress']*100)}%)"
    status = _registry.get_status(run_id, message=message)
    if status is None:
        return RunStatusResponse(runId=run_id, status=RunStatusEnum.FAILED, message="Run not found", progress=0.0)
    return status


# -------- Team config --------


@router.get("/team", summary="获取队伍配置")
def get_team():
    """
    获取所有预设队伍的配置信息

    ## 功能描述
    返回系统中配置的所有预设队伍信息，包括队伍成员和自动战斗配置。

    ## 返回数据
    - **teams**: 队伍配置列表
      - **idx**: 队伍索引
      - **name**: 队伍名称
      - **members**: 队伍成员列表
        - **agentId**: 代理人ID
        - **name**: 代理人名称
      - **autoBattle**: 自动战斗配置

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/onedragon/team")
    teams = response.json()
    for team in teams['teams']:
        print(f"队伍 {team['name']}: {[m['name'] for m in team['members']]}")
    ```
    """
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


@router.get("/apps", summary="获取一条龙应用列表")
def get_apps():
    """
    获取一条龙可运行的应用清单

    ## 功能描述
    返回一条龙系统中所有可用的应用模块，包括应用的启用状态和执行顺序。

    ## 返回数据
    - **items**: 应用列表
      - **appId**: 应用唯一标识符
      - **name**: 应用显示名称
      - **enabled**: 是否启用该应用
      - **orderIndex**: 执行顺序索引
    - **appOrder**: 应用执行顺序数组（兼容字段）
    - **appRunList**: 启用的应用ID列表（兼容字段）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/onedragon/apps")
    apps = response.json()
    enabled_apps = [app for app in apps['items'] if app['enabled']]
    print(f"启用的应用: {[app['name'] for app in enabled_apps]}")
    ```
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


@router.put("/apps", summary="更新一条龙应用配置")
def update_apps(payload: dict):
    """
    更新一条龙应用的顺序和运行列表

    ## 功能描述
    批量更新一条龙应用的执行顺序和启用状态。

    ## 请求参数
    - **items** (可选): 应用配置列表
      - **appId**: 应用ID
      - **enabled**: 是否启用
      - **orderIndex**: 执行顺序
    - **appOrder** (可选): 应用执行顺序数组（兼容字段）
    - **appRunList** (可选): 启用的应用ID列表（兼容字段）

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "items": [
            {"appId": "charge_plan", "enabled": True, "orderIndex": 0},
            {"appId": "coffee", "enabled": False, "orderIndex": 1}
        ]
    }
    response = requests.put("http://localhost:8000/api/v1/onedragon/apps", json=data)
    ```
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


@router.post("/charge-plan/run", response_model=dict, summary="运行体力计划")
async def run_charge_plan():
    """
    单独运行体力计划任务

    ## 功能描述
    启动体力计划的单独执行任务，按照当前配置的体力计划列表执行。

    ## 返回数据
    - **runId**: 任务运行ID

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/charge-plan/run")
    task_info = response.json()
    print(f"体力计划任务ID: {task_info['runId']}")
    ```
    """
    run_id = _run_via_onedragon_with_temp(["charge_plan"])  # app_id 按实际定义
    return {"runId": run_id}


@router.post("/notorious-hunt/run", response_model=dict, summary="运行恶名狩猎")
async def run_notorious_hunt():
    """
    单独运行恶名狩猎任务

    ## 功能描述
    启动恶名狩猎的单独执行任务，按照当前配置的恶名狩猎计划执行。

    ## 返回数据
    - **runId**: 任务运行ID

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/notorious-hunt/run")
    task_info = response.json()
    print(f"恶名狩猎任务ID: {task_info['runId']}")
    ```
    """
    run_id = _run_via_onedragon_with_temp(["notorious_hunt"])  # 以 GUI 内部 app_id 为准
    return {"runId": run_id}


@router.post("/coffee-plan/run", response_model=dict, summary="运行咖啡计划")
async def run_coffee_plan():
    """
    单独运行咖啡计划任务

    ## 功能描述
    启动咖啡计划的单独执行任务，按照当前配置的咖啡计划执行。

    ## 返回数据
    - **runId**: 任务运行ID

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/coffee-plan/run")
    task_info = response.json()
    print(f"咖啡计划任务ID: {task_info['runId']}")
    ```
    """
    run_id = _run_via_onedragon_with_temp(["coffee"])  # 以 GUI 内部 app_id 为准
    return {"runId": run_id}


@router.post("/shiyu-defense/run", response_model=dict, summary="运行式舆防卫战")
async def run_shiyu_defense():
    """
    单独运行式舆防卫战任务

    ## 功能描述
    启动式舆防卫战的单独执行任务，按照当前配置的队伍和策略执行。

    ## 返回数据
    - **runId**: 任务运行ID

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/shiyu-defense/run")
    task_info = response.json()
    print(f"式舆防卫战任务ID: {task_info['runId']}")
    ```
    """
    run_id = _run_via_onedragon_with_temp(["shiyu_defense"])  # 以 GUI 内部 app_id 为准
    return {"runId": run_id}


# 可选：通用按 appId 运行（前端可直接调用）
@router.post("/apps/{appId}:run", response_model=dict, summary="运行指定应用")
async def run_app_by_id(appId: str):
    """
    运行指定ID的应用模块

    ## 功能描述
    通过应用ID启动特定的应用模块执行任务。

    ## 路径参数
    - **appId**: 要运行的应用ID

    ## 返回数据
    - **runId**: 任务运行ID

    ## 错误码
    - **INVALID_APP_ID**: 应用ID无效
    - **APP_NOT_FOUND**: 应用不存在

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/apps/charge_plan:run")
    task_info = response.json()
    print(f"应用任务ID: {task_info['runId']}")
    ```
    """
    # 统一通过一条龙运行，确保进/出游戏与实例切换等流程完整
    run_id = _run_via_onedragon_with_temp([appId])
    return {"runId": run_id}


# 兼容路由：/apps/{appId}/run 与 /run-app/{appId}
@router.post("/apps/{appId}/run", response_model=dict, summary="运行指定应用（别名路径）")
async def run_app_alias_path(appId: str):
    """
    运行指定ID的应用模块（别名路径）

    ## 功能描述
    通过应用ID启动特定的应用模块执行任务。这是 `/apps/{appId}:run` 的别名路径。

    ## 路径参数
    - **appId**: 要运行的应用ID

    ## 返回数据
    - **runId**: 任务运行ID

    ## 错误码
    - **INVALID_APP_ID**: 应用ID无效
    - **APP_NOT_FOUND**: 应用不存在

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/apps/charge_plan/run")
    task_info = response.json()
    print(f"应用任务ID: {task_info['runId']}")
    ```
    """
    return await run_app_by_id(appId)


@router.post("/run-app/{appId}", response_model=dict, summary="运行指定应用（兼容路径）")
async def run_app_alias_legacy(appId: str):
    """
    运行指定ID的应用模块（兼容路径）

    ## 功能描述
    通过应用ID启动特定的应用模块执行任务。这是为了兼容旧版本API而保留的路径。

    ## 路径参数
    - **appId**: 要运行的应用ID

    ## 返回数据
    - **runId**: 任务运行ID

    ## 错误码
    - **INVALID_APP_ID**: 应用ID无效
    - **APP_NOT_FOUND**: 应用不存在

    ## 注意事项
    - 这是兼容性API，建议使用 `/apps/{appId}:run` 或 `/apps/{appId}/run`

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/run-app/charge_plan")
    task_info = response.json()
    print(f"应用任务ID: {task_info['runId']}")
    ```
    """
    return await run_app_by_id(appId)


@router.put("/team", summary="更新队伍配置")
def update_team(payload: dict):
    """
    更新预设队伍的配置信息

    ## 功能描述
    批量更新预设队伍的配置，包括队伍成员和自动战斗设置。

    ## 请求参数
    - **teams**: 队伍配置列表
      - **idx**: 队伍索引
      - **name** (可选): 队伍名称，默认"编队{idx+1}"
      - **members** (可选): 队伍成员ID列表
      - **autoBattle** (可选): 自动战斗配置，默认"全配队通用"

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "teams": [
            {
                "idx": 0,
                "name": "主力队伍",
                "members": ["agent1", "agent2", "agent3"],
                "autoBattle": "全配队通用"
            }
        ]
    }
    response = requests.put("http://localhost:8000/api/v1/onedragon/team", json=data)
    ```
    """
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


@router.put("/apps/{app_id}", summary="设置应用启用状态")
def set_onedragon_app_enabled(app_id: str, payload: dict):
    """
    设置指定应用的启用状态

    ## 功能描述
    启用或禁用指定的一条龙应用模块，控制该应用是否参与一条龙任务执行。

    ## 路径参数
    - **app_id**: 应用ID

    ## 请求参数
    - **toRun**: 是否启用该应用，布尔值，默认true

    ## 返回数据
    - **ok**: 操作是否成功

    ## 错误码
    - **INVALID_APP_ID**: 应用ID无效
    - **APP_NOT_FOUND**: 应用不存在

    ## 使用示例
    ```python
    import requests
    # 启用应用
    data = {"toRun": True}
    response = requests.put("http://localhost:8000/api/v1/onedragon/apps/charge_plan", json=data)

    # 禁用应用
    data = {"toRun": False}
    response = requests.put("http://localhost:8000/api/v1/onedragon/apps/coffee", json=data)
    ```
    """
    ctx = get_ctx()
    to_run = bool(payload.get("toRun", True))
    ctx.one_dragon_app_config.set_app_run(app_id, to_run)
    return {"ok": True}


@router.post("/apps:reorder", summary="重新排序应用")
def reorder_onedragon_apps(payload: dict):
    """
    重新排序一条龙应用的执行顺序

    ## 功能描述
    调整一条龙应用列表中应用的执行顺序，支持上移和置顶操作。

    ## 请求参数
    - **mode**: 操作模式
      - "move_up": 上移一位
      - "move_top": 移动到顶部
    - **appId**: 要移动的应用ID

    ## 返回数据
    - **ok**: 操作是否成功
    - **error** (失败时): 错误信息
      - **code**: 错误代码
      - **message**: 错误消息

    ## 错误码
    - **INVALID_ARGUMENT**: 缺少必需参数appId
    - **UNSUPPORTED_MODE**: 不支持的操作模式
    - **APP_NOT_FOUND**: 应用不存在

    ## 使用示例
    ```python
    import requests
    # 将应用上移一位
    data = {"mode": "move_up", "appId": "charge_plan"}
    response = requests.post("http://localhost:8000/api/v1/onedragon/apps:reorder", json=data)

    # 将应用移到顶部
    data = {"mode": "move_top", "appId": "coffee"}
    response = requests.post("http://localhost:8000/api/v1/onedragon/apps:reorder", json=data)
    ```
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


@router.post("/run-app/{app_id}", response_model=RunIdResponse, summary="运行单个应用")
async def run_single_app(app_id: str):
    """
    运行单个一条龙子应用

    ## 功能描述
    仅运行指定的单个一条龙子应用模块，不执行其他应用。使用临时运行列表确保只执行指定应用。

    ## 路径参数
    - **app_id**: 要运行的应用ID

    ## 返回数据
    - **runId**: 任务运行ID

    ## 错误码
    - **INVALID_APP_ID**: 应用ID无效
    - **APP_NOT_FOUND**: 应用不存在
    - **TASK_START_FAILED**: 任务启动失败

    ## 注意事项
    - 此API会临时修改运行列表，执行完成后自动恢复
    - 与 `/apps/{appId}:run` 功能相同，但实现方式不同

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/onedragon/run-app/charge_plan")
    task_info = response.json()
    print(f"单应用任务ID: {task_info['runId']}")
    ```
    """
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


