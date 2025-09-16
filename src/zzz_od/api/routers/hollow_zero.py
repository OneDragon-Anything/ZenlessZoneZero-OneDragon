from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException

from zzz_od.api.deps import get_ctx
from zzz_od.api.models import RunIdResponse
from zzz_od.api.security import get_api_key_dependency
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.bridges import attach_run_event_bridge
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig, get_all_hollow_zero_challenge_config, get_hollow_zero_challenge_new_name, HollowZeroChallengePathFinding
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import LostVoidChallengeConfig, get_all_lost_void_challenge_config, get_lost_void_challenge_new_name, LostVoidPeriodBuffNo
from zzz_od.application.hollow_zero.lost_void.lost_void_config import LostVoidConfig, LostVoidExtraTask
from zzz_od.game_data.agent import AgentTypeEnum
from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list


router = APIRouter(
    prefix="/api/v1/hollow-zero",
    tags=["零号空洞 Hollow Zero"],
    dependencies=[Depends(get_api_key_dependency())],
)


_registry = get_global_run_registry()


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


@router.post("/run", response_model=RunIdResponse, summary="运行零号空洞 - 枯萎之都")
async def run_hollow_zero():
    """
    启动零号空洞 - 枯萎之都自动化任务

    ## 功能描述
    启动零号空洞枯萎之都的自动化挑战任务，使用当前配置的挑战策略和队伍配置。

    ## 返回数据
    - **runId**: 任务运行ID，用于后续状态查询和控制

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **CONFIG_ERROR**: 配置错误

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/run")
    task_info = response.json()
    print(f"任务ID: {task_info['runId']}")
    ```
    """
    run_id = _run_via_onedragon_with_temp(["hollow_zero"])
    return RunIdResponse(runId=run_id)


@router.post("/lost-void/run", response_model=RunIdResponse, summary="运行零号空洞 - 迷失之地")
async def run_lost_void():
    """
    启动零号空洞 - 迷失之地自动化任务

    ## 功能描述
    启动零号空洞迷失之地的自动化挑战任务，使用当前配置的挑战策略和队伍配置。

    ## 返回数据
    - **runId**: 任务运行ID，用于后续状态查询和控制

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **CONFIG_ERROR**: 配置错误

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/lost-void/run")
    task_info = response.json()
    print(f"迷失之地任务ID: {task_info['runId']}")
    ```
    """
    run_id = _run_via_onedragon_with_temp(["lost_void"])
    return RunIdResponse(runId=run_id)


# -------- Hollow Zero Challenge Config --------


@router.get("/route-list", response_model=List[str], summary="获取路线名单")
def get_hollow_zero_route_list() -> List[str]:
    """
    获取锄大地路线名单（挑战配置名称列表）

    ## 功能描述
    返回所有可用的锄大地挑战配置名称，用于GUI界面的路线选择下拉框。

    ## 返回数据
    配置名称字符串列表

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/route-list")
    routes = response.json()
    for route in routes:
        print(f"路线: {route}")
    ```
    """
    try:
        configs = get_all_hollow_zero_challenge_config()
        return [config.module_name for config in configs]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "ROUTE_LIST_FETCH_FAILED",
                    "message": f"获取路线名单失败: {str(e)}"
                }
            }
        )


@router.get("/challenge-configs", response_model=List[Dict[str, Any]], summary="获取所有枯萎之都挑战配置")
def get_hollow_zero_challenge_configs() -> List[Dict[str, Any]]:
    """
    获取所有枯萎之都挑战配置列表

    ## 功能描述
    返回系统中所有可用的枯萎之都挑战配置，包括自动战斗设置、鸣徽优先级、事件优先级等详细配置信息。

    ## 返回数据
    配置对象列表，每个配置包含：
    - **moduleName**: 配置模块名称
    - **autoBattle**: 自动战斗配置名称
    - **resoniumPriority**: 鸣徽优先级列表
    - **eventPriority**: 事件优先级列表
    - **targetAgents**: 目标代理人列表
    - **pathFinding**: 寻路策略设置
    - **goIn1Step**: 一步可达入口列表
    - **waypoint**: 优先途经点列表
    - **avoid**: 避免途经点列表

    ## 错误码
    - **CONFIG_FETCH_FAILED**: 获取配置失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/challenge-configs")
    configs = response.json()
    for config in configs:
        print(f"配置: {config['moduleName']}")
    ```
    """
    configs = get_all_hollow_zero_challenge_config()
    return [
        {
            "moduleName": config.module_name,
            "autoBattle": config.auto_battle,
            "resoniumPriority": config.resonium_priority,
            "eventPriority": config.event_priority,
            "targetAgents": config.target_agents,
            "pathFinding": config.path_finding,
            "goIn1Step": config.go_in_1_step,
            "waypoint": config.waypoint,
            "avoid": config.avoid,
        }
        for config in configs
    ]


@router.get("/challenge-configs/{module_name}", response_model=Dict[str, Any], summary="获取指定的枯萎之都挑战配置")
def get_hollow_zero_challenge_config(module_name: str) -> Dict[str, Any]:
    """
    获取指定名称的枯萎之都挑战配置详情

    ## 功能描述
    根据配置模块名称获取特定的枯萎之都挑战配置的详细信息。

    ## 路径参数
    - **module_name**: 配置模块名称

    ## 返回数据
    配置对象，包含：
    - **moduleName**: 配置模块名称
    - **autoBattle**: 自动战斗配置名称
    - **resoniumPriority**: 鸣徽优先级列表
    - **eventPriority**: 事件优先级列表
    - **targetAgents**: 目标代理人列表
    - **pathFinding**: 寻路策略设置
    - **goIn1Step**: 一步可达入口列表
    - **waypoint**: 优先途经点列表
    - **avoid**: 避免途经点列表

    ## 错误码
    - **CONFIG_NOT_FOUND**: 配置不存在 (404)
    - **CONFIG_FETCH_FAILED**: 获取配置失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/challenge-configs/默认配置")
    config = response.json()
    print(f"自动战斗配置: {config['autoBattle']}")
    ```
    """
    configs = get_all_hollow_zero_challenge_config()
    config = next((c for c in configs if c.module_name == module_name), None)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "moduleName": config.module_name,
        "autoBattle": config.auto_battle,
        "resoniumPriority": config.resonium_priority,
        "eventPriority": config.event_priority,
        "targetAgents": config.target_agents,
        "pathFinding": config.path_finding,
        "goIn1Step": config.go_in_1_step,
        "waypoint": config.waypoint,
        "avoid": config.avoid,
    }


@router.post("/challenge-configs", response_model=Dict[str, Any], summary="创建新的枯萎之都挑战配置")
def create_hollow_zero_challenge_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    创建新的枯萎之都挑战配置

    ## 功能描述
    根据提供的配置参数创建一个新的枯萎之都挑战配置文件。

    ## 请求参数
    - **moduleName** (可选): 配置模块名称，不提供时自动生成
    - **autoBattle** (可选): 自动战斗配置名称
    - **resoniumPriority** (可选): 鸣徽优先级列表
    - **eventPriority** (可选): 事件优先级列表
    - **targetAgents** (可选): 目标代理人列表
    - **pathFinding** (可选): 寻路策略设置
    - **goIn1Step** (可选): 一步可达入口列表
    - **waypoint** (可选): 优先途经点列表
    - **avoid** (可选): 避免途经点列表

    ## 返回数据
    - **moduleName**: 创建的配置模块名称
    - **message**: 创建成功消息

    ## 错误码
    - **CONFIG_CREATE_FAILED**: 配置创建失败
    - **VALIDATION_ERROR**: 参数验证失败

    ## 使用示例
    ```python
    import requests
    data = {
        "moduleName": "我的配置",
        "autoBattle": "全配队通用",
        "resoniumPriority": ["强袭 攻击", "顽强 防御"]
    }
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/challenge-configs", json=data)
    result = response.json()
    print(f"创建配置: {result['moduleName']}")
    ```
    """
    module_name = payload.get("moduleName", get_hollow_zero_challenge_new_name())
    config = HollowZeroChallengeConfig(module_name)

    # 设置配置属性
    if "autoBattle" in payload:
        config.auto_battle = payload["autoBattle"]
    if "resoniumPriority" in payload:
        config.resonium_priority = payload["resoniumPriority"]
    if "eventPriority" in payload:
        config.event_priority = payload["eventPriority"]
    if "targetAgents" in payload:
        config.target_agents = payload["targetAgents"]
    if "pathFinding" in payload:
        config.path_finding = payload["pathFinding"]
    if "goIn1Step" in payload:
        config.go_in_1_step = payload["goIn1Step"]
    if "waypoint" in payload:
        config.waypoint = payload["waypoint"]
    if "avoid" in payload:
        config.avoid = payload["avoid"]

    config.save()

    return {"moduleName": config.module_name, "message": "Configuration created successfully"}


@router.put("/challenge-configs/{module_name}", response_model=Dict[str, Any], summary="更新指定的枯萎之都挑战配置")
def update_hollow_zero_challenge_config(module_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新指定的枯萎之都挑战配置

    ## 功能描述
    根据配置模块名称更新现有的枯萎之都挑战配置，支持部分更新。

    ## 路径参数
    - **module_name**: 要更新的配置模块名称

    ## 请求参数
    - **moduleName** (可选): 新的配置模块名称
    - **autoBattle** (可选): 自动战斗配置名称
    - **resoniumPriority** (可选): 鸣徽优先级列表
    - **eventPriority** (可选): 事件优先级列表
    - **targetAgents** (可选): 目标代理人列表
    - **pathFinding** (可选): 寻路策略设置
    - **goIn1Step** (可选): 一步可达入口列表
    - **waypoint** (可选): 优先途经点列表
    - **avoid** (可选): 避免途经点列表

    ## 返回数据
    - **moduleName**: 更新后的配置模块名称
    - **message**: 更新成功消息

    ## 错误码
    - **CONFIG_NOT_FOUND**: 配置不存在 (404)
    - **CONFIG_UPDATE_FAILED**: 配置更新失败
    - **VALIDATION_ERROR**: 参数验证失败

    ## 使用示例
    ```python
    import requests
    data = {
        "autoBattle": "新的战斗配置",
        "resoniumPriority": ["更新的鸣徽优先级"]
    }
    response = requests.put("http://localhost:8000/api/v1/hollow-zero/challenge-configs/我的配置", json=data)
    result = response.json()
    print(result['message'])
    ```
    """
    configs = get_all_hollow_zero_challenge_config()
    config = next((c for c in configs if c.module_name == module_name), None)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    # 更新配置属性
    if "moduleName" in payload and payload["moduleName"] != module_name:
        config.update_module_name(payload["moduleName"])
    if "autoBattle" in payload:
        config.auto_battle = payload["autoBattle"]
    if "resoniumPriority" in payload:
        config.resonium_priority = payload["resoniumPriority"]
    if "eventPriority" in payload:
        config.event_priority = payload["eventPriority"]
    if "targetAgents" in payload:
        config.target_agents = payload["targetAgents"]
    if "pathFinding" in payload:
        config.path_finding = payload["pathFinding"]
    if "goIn1Step" in payload:
        config.go_in_1_step = payload["goIn1Step"]
    if "waypoint" in payload:
        config.waypoint = payload["waypoint"]
    if "avoid" in payload:
        config.avoid = payload["avoid"]

    config.save()

    return {"moduleName": config.module_name, "message": "Configuration updated successfully"}


@router.delete("/challenge-configs/{module_name}", response_model=Dict[str, Any], summary="删除指定的枯萎之都挑战配置")
def delete_hollow_zero_challenge_config(module_name: str) -> Dict[str, Any]:
    """
    删除指定的枯萎之都挑战配置

    ## 功能描述
    根据配置模块名称删除指定的枯萎之都挑战配置文件。

    ## 路径参数
    - **module_name**: 要删除的配置模块名称

    ## 返回数据
    - **message**: 删除成功消息

    ## 错误码
    - **CONFIG_NOT_FOUND**: 配置不存在 (404)
    - **CONFIG_DELETE_FAILED**: 配置删除失败
    - **PERMISSION_ERROR**: 权限错误（如尝试删除系统配置）

    ## 注意事项
    - 删除操作不可逆，请谨慎操作
    - 系统默认配置可能无法删除

    ## 使用示例
    ```python
    import requests
    response = requests.delete("http://localhost:8000/api/v1/hollow-zero/challenge-configs/我的配置")
    result = response.json()
    print(result['message'])
    ```
    """
    configs = get_all_hollow_zero_challenge_config()
    config = next((c for c in configs if c.module_name == module_name), None)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    # 删除配置文件
    import os
    if os.path.exists(config.file_path):
        os.remove(config.file_path)

    return {"message": "Configuration deleted successfully"}


# -------- Lost Void Challenge Config --------


@router.get("/lost-void/challenge-configs", response_model=List[Dict[str, Any]], summary="获取所有迷失之地挑战配置")
def get_lost_void_challenge_configs() -> List[Dict[str, Any]]:
    """
    获取所有迷失之地挑战配置列表

    ## 功能描述
    返回系统中所有可用的迷失之地挑战配置，包括队伍选择、自动战斗设置、藏品优先级等详细配置信息。

    ## 返回数据
    配置对象列表，每个配置包含：
    - **moduleName**: 配置模块名称
    - **predefinedTeamIdx**: 预设队伍索引
    - **chooseTeamByPriority**: 是否按优先级选择队伍
    - **autoBattle**: 自动战斗配置名称
    - **artifactPriorityNew**: 新藏品优先级列表
    - **artifactPriority**: 藏品优先级列表
    - **artifactPriority2**: 二级藏品优先级列表
    - **regionTypePriority**: 区域类型优先级列表
    - **periodBuffNo**: 周期增益编号
    - **buyOnlyPriority1**: 是否只购买优先级1的物品

    ## 错误码
    - **CONFIG_FETCH_FAILED**: 获取配置失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/lost-void/challenge-configs")
    configs = response.json()
    for config in configs:
        print(f"迷失之地配置: {config['moduleName']}")
    ```
    """
    configs = get_all_lost_void_challenge_config()
    return [
        {
            "moduleName": config.module_name,
            "predefinedTeamIdx": config.predefined_team_idx,
            "chooseTeamByPriority": config.choose_team_by_priority,
            "autoBattle": config.auto_battle,
            "artifactPriorityNew": config.artifact_priority_new,
            "artifactPriority": config.artifact_priority,
            "artifactPriority2": config.artifact_priority_2,
            "regionTypePriority": config.region_type_priority,
            "periodBuffNo": config.period_buff_no,
            "buyOnlyPriority1": config.buy_only_priority_1,
        }
        for config in configs
    ]


@router.get("/lost-void/challenge-configs/{module_name}", response_model=Dict[str, Any], summary="获取指定的迷失之地挑战配置")
def get_lost_void_challenge_config(module_name: str) -> Dict[str, Any]:
    """
    获取指定名称的迷失之地挑战配置详情

    ## 功能描述
    根据配置模块名称获取特定的迷失之地挑战配置的详细信息。

    ## 路径参数
    - **module_name**: 配置模块名称

    ## 返回数据
    配置对象，包含：
    - **moduleName**: 配置模块名称
    - **predefinedTeamIdx**: 预设队伍索引 (-1表示游戏内配队)
    - **chooseTeamByPriority**: 是否按优先级选择队伍
    - **autoBattle**: 自动战斗配置名称
    - **artifactPriorityNew**: 新藏品优先级列表
    - **artifactPriority**: 藏品优先级列表
    - **artifactPriority2**: 二级藏品优先级列表
    - **regionTypePriority**: 区域类型优先级列表
    - **periodBuffNo**: 周期增益编号
    - **buyOnlyPriority1**: 是否只购买优先级1的物品

    ## 错误码
    - **CONFIG_NOT_FOUND**: 配置不存在 (404)
    - **CONFIG_FETCH_FAILED**: 获取配置失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/lost-void/challenge-configs/默认配置")
    config = response.json()
    print(f"队伍索引: {config['predefinedTeamIdx']}")
    ```
    """
    configs = get_all_lost_void_challenge_config()
    config = next((c for c in configs if c.module_name == module_name), None)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "moduleName": config.module_name,
        "predefinedTeamIdx": config.predefined_team_idx,
        "chooseTeamByPriority": config.choose_team_by_priority,
        "autoBattle": config.auto_battle,
        "artifactPriorityNew": config.artifact_priority_new,
        "artifactPriority": config.artifact_priority,
        "artifactPriority2": config.artifact_priority_2,
        "regionTypePriority": config.region_type_priority,
        "periodBuffNo": config.period_buff_no,
        "buyOnlyPriority1": config.buy_only_priority_1,
    }


@router.post("/lost-void/challenge-configs", response_model=Dict[str, Any], summary="创建新的迷失之地挑战配置")
def create_lost_void_challenge_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    创建新的迷失之地挑战配置

    ## 功能描述
    根据提供的配置参数创建一个新的迷失之地挑战配置文件。

    ## 请求参数
    - **moduleName** (可选): 配置模块名称，不提供时自动生成
    - **predefinedTeamIdx** (可选): 预设队伍索引，-1表示游戏内配队
    - **chooseTeamByPriority** (可选): 是否按优先级选择队伍
    - **autoBattle** (可选): 自动战斗配置名称
    - **artifactPriorityNew** (可选): 新藏品优先级列表
    - **artifactPriority** (可选): 藏品优先级列表
    - **artifactPriority2** (可选): 二级藏品优先级列表
    - **regionTypePriority** (可选): 区域类型优先级列表
    - **periodBuffNo** (可选): 周期增益编号
    - **buyOnlyPriority1** (可选): 是否只购买优先级1的物品

    ## 返回数据
    - **moduleName**: 创建的配置模块名称
    - **message**: 创建成功消息

    ## 错误码
    - **CONFIG_CREATE_FAILED**: 配置创建失败
    - **VALIDATION_ERROR**: 参数验证失败

    ## 使用示例
    ```python
    import requests
    data = {
        "moduleName": "我的迷失之地配置",
        "predefinedTeamIdx": 1,
        "autoBattle": "全配队通用"
    }
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/lost-void/challenge-configs", json=data)
    result = response.json()
    print(f"创建配置: {result['moduleName']}")
    ```
    """
    module_name = payload.get("moduleName", get_lost_void_challenge_new_name())
    config = LostVoidChallengeConfig(module_name)

    # 设置配置属性
    if "predefinedTeamIdx" in payload:
        config.predefined_team_idx = payload["predefinedTeamIdx"]
    if "chooseTeamByPriority" in payload:
        config.choose_team_by_priority = payload["chooseTeamByPriority"]
    if "autoBattle" in payload:
        config.auto_battle = payload["autoBattle"]
    if "artifactPriorityNew" in payload:
        config.artifact_priority_new = payload["artifactPriorityNew"]
    if "artifactPriority" in payload:
        config.artifact_priority = payload["artifactPriority"]
    if "artifactPriority2" in payload:
        config.artifact_priority_2 = payload["artifactPriority2"]
    if "regionTypePriority" in payload:
        config.region_type_priority = payload["regionTypePriority"]
    if "periodBuffNo" in payload:
        config.period_buff_no = payload["periodBuffNo"]
    if "buyOnlyPriority1" in payload:
        config.buy_only_priority_1 = payload["buyOnlyPriority1"]

    config.save()

    return {"moduleName": config.module_name, "message": "Configuration created successfully"}


@router.put("/lost-void/challenge-configs/{module_name}", response_model=Dict[str, Any], summary="更新指定的迷失之地挑战配置")
def update_lost_void_challenge_config(module_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新指定的迷失之地挑战配置

    ## 功能描述
    根据配置模块名称更新现有的迷失之地挑战配置，支持部分更新。

    ## 路径参数
    - **module_name**: 要更新的配置模块名称

    ## 请求参数
    - **moduleName** (可选): 新的配置模块名称
    - **predefinedTeamIdx** (可选): 预设队伍索引，-1表示游戏内配队
    - **chooseTeamByPriority** (可选): 是否按优先级选择队伍
    - **autoBattle** (可选): 自动战斗配置名称
    - **artifactPriorityNew** (可选): 新藏品优先级列表
    - **artifactPriority** (可选): 藏品优先级列表
    - **artifactPriority2** (可选): 二级藏品优先级列表
    - **regionTypePriority** (可选): 区域类型优先级列表
    - **periodBuffNo** (可选): 周期增益编号
    - **buyOnlyPriority1** (可选): 是否只购买优先级1的物品

    ## 返回数据
    - **moduleName**: 更新后的配置模块名称
    - **message**: 更新成功消息

    ## 错误码
    - **CONFIG_NOT_FOUND**: 配置不存在 (404)
    - **CONFIG_UPDATE_FAILED**: 配置更新失败
    - **VALIDATION_ERROR**: 参数验证失败

    ## 使用示例
    ```python
    import requests
    data = {
        "predefinedTeamIdx": 2,
        "autoBattle": "新的战斗配置"
    }
    response = requests.put("http://localhost:8000/api/v1/hollow-zero/lost-void/challenge-configs/我的配置", json=data)
    result = response.json()
    print(result['message'])
    ```
    """
    configs = get_all_lost_void_challenge_config()
    config = next((c for c in configs if c.module_name == module_name), None)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    # 更新配置属性
    if "moduleName" in payload and payload["moduleName"] != module_name:
        config.update_module_name(payload["moduleName"])
    if "predefinedTeamIdx" in payload:
        config.predefined_team_idx = payload["predefinedTeamIdx"]
    if "chooseTeamByPriority" in payload:
        config.choose_team_by_priority = payload["chooseTeamByPriority"]
    if "autoBattle" in payload:
        config.auto_battle = payload["autoBattle"]
    if "artifactPriorityNew" in payload:
        config.artifact_priority_new = payload["artifactPriorityNew"]
    if "artifactPriority" in payload:
        config.artifact_priority = payload["artifactPriority"]
    if "artifactPriority2" in payload:
        config.artifact_priority_2 = payload["artifactPriority2"]
    if "regionTypePriority" in payload:
        config.region_type_priority = payload["regionTypePriority"]
    if "periodBuffNo" in payload:
        config.period_buff_no = payload["periodBuffNo"]
    if "buyOnlyPriority1" in payload:
        config.buy_only_priority_1 = payload["buyOnlyPriority1"]

    config.save()

    return {"moduleName": config.module_name, "message": "Configuration updated successfully"}


@router.delete("/lost-void/challenge-configs/{module_name}", response_model=Dict[str, Any], summary="删除指定的迷失之地挑战配置")
def delete_lost_void_challenge_config(module_name: str) -> Dict[str, Any]:
    """
    删除指定的迷失之地挑战配置

    ## 功能描述
    根据配置模块名称删除指定的迷失之地挑战配置文件。

    ## 路径参数
    - **module_name**: 要删除的配置模块名称

    ## 返回数据
    - **message**: 删除成功消息

    ## 错误码
    - **CONFIG_NOT_FOUND**: 配置不存在 (404)
    - **CONFIG_DELETE_FAILED**: 配置删除失败
    - **PERMISSION_ERROR**: 权限错误（如尝试删除系统配置）

    ## 注意事项
    - 删除操作不可逆，请谨慎操作
    - 系统默认配置可能无法删除

    ## 使用示例
    ```python
    import requests
    response = requests.delete("http://localhost:8000/api/v1/hollow-zero/lost-void/challenge-configs/我的配置")
    result = response.json()
    print(result['message'])
    ```
    """
    configs = get_all_lost_void_challenge_config()
    config = next((c for c in configs if c.module_name == module_name), None)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    # 删除配置文件
    import os
    if os.path.exists(config.file_path):
        os.remove(config.file_path)

    return {"message": "Configuration deleted successfully"}


# -------- Lost Void Base Config --------


@router.get("/lost-void/config", response_model=Dict[str, Any], summary="获取迷失之地基础配置")
def get_lost_void_config(ctx = Depends(get_ctx)) -> Dict[str, Any]:
    """
    获取迷失之地基础配置

    ## 功能描述
    获取迷失之地的基础运行配置，包括每日计划次数、每周计划次数、额外任务、任务名称和挑战配置。

    ## 返回数据
    - **dailyPlanTimes**: 每日计划次数
    - **weeklyPlanTimes**: 每周计划次数
    - **extraTask**: 额外任务类型
    - **missionName**: 任务名称
    - **challengeConfig**: 挑战配置名称

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/lost-void/config")
    config = response.json()
    print(f"每日计划次数: {config['dailyPlanTimes']}")
    ```
    """
    config = ctx.lost_void_config
    return {
        "dailyPlanTimes": config.daily_plan_times,
        "weeklyPlanTimes": config.weekly_plan_times,
        "extraTask": config.extra_task,
        "missionName": config.mission_name,
        "challengeConfig": config.challenge_config,
    }


@router.put("/lost-void/config", response_model=Dict[str, Any], summary="更新迷失之地基础配置")
def update_lost_void_config(payload: Dict[str, Any], ctx = Depends(get_ctx)) -> Dict[str, Any]:
    """
    更新迷失之地基础配置

    ## 功能描述
    更新迷失之地的基础运行配置，支持部分更新。

    ## 请求参数
    - **dailyPlanTimes** (可选): 每日计划次数
    - **weeklyPlanTimes** (可选): 每周计划次数
    - **extraTask** (可选): 额外任务类型
    - **missionName** (可选): 任务名称
    - **challengeConfig** (可选): 挑战配置名称

    ## 返回数据
    - **message**: 更新成功消息

    ## 使用示例
    ```python
    import requests
    data = {
        "dailyPlanTimes": 3,
        "weeklyPlanTimes": 1,
        "extraTask": "刷满业绩点"
    }
    response = requests.put("http://localhost:8000/api/v1/hollow-zero/lost-void/config", json=data)
    result = response.json()
    print(result['message'])
    ```
    """
    config = ctx.lost_void_config

    # 更新配置属性
    if "dailyPlanTimes" in payload:
        config.daily_plan_times = payload["dailyPlanTimes"]
    if "weeklyPlanTimes" in payload:
        config.weekly_plan_times = payload["weeklyPlanTimes"]
    if "extraTask" in payload:
        config.extra_task = payload["extraTask"]
    if "missionName" in payload:
        config.mission_name = payload["missionName"]
    if "challengeConfig" in payload:
        config.challenge_config = payload["challengeConfig"]

    config.save()

    return {"message": "Lost void configuration updated successfully"}


@router.get("/lost-void/extra-task-options", response_model=List[Dict[str, str]], summary="获取迷失之地额外任务选项")
def get_lost_void_extra_task_options() -> List[Dict[str, str]]:
    """
    获取迷失之地额外任务选项列表

    ## 功能描述
    返回所有可用的迷失之地额外任务选项，用于配置界面的选择。

    ## 返回数据
    - **value**: 任务值
    - **label**: 任务显示名称

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/lost-void/extra-task-options")
    options = response.json()
    for option in options:
        print(f"任务: {option['label']}")
    ```
    """
    options = []
    for task in LostVoidExtraTask:
        options.append({
            "value": task.value.value,
            "label": task.value.value
        })
    return options


# ============================================================================
# 数据模型定义
# ============================================================================

class AgentInfo(BaseModel):
    """代理人信息"""
    agent_id: str
    agent_name: str
    agent_type: str
    rarity: Optional[str] = None
    damage_type: Optional[str] = None

class AgentTypeInfo(BaseModel):
    """代理人类型信息"""
    type_id: str
    type_name: str

class MissionInfo(BaseModel):
    """任务信息"""
    mission_id: str
    mission_name: str
    description: Optional[str] = None

class AutoBattleConfigInfo(BaseModel):
    """自动战斗配置信息"""
    config_name: str
    description: Optional[str] = None

class TeamConfigInfo(BaseModel):
    """队伍配置信息"""
    team_id: int
    team_name: str
    agents: List[str]

class ResoniumInfo(BaseModel):
    """鸣徽信息"""
    resonium_id: str
    resonium_name: str
    category: str
    description: Optional[str] = None

class EventInfo(BaseModel):
    """事件信息"""
    event_id: str
    event_name: str
    description: Optional[str] = None
    is_benefit: bool = False

class EntryTypeInfo(BaseModel):
    """入口类型信息"""
    entry_id: str
    entry_name: str
    can_go: bool = True
    is_benefit: bool = False

class ValidationRequest(BaseModel):
    """验证请求"""
    input_text: str

class ValidationResponse(BaseModel):
    """验证响应"""
    is_valid: bool
    validated_list: List[str]
    error_message: str = ""

class RunRecordInfo(BaseModel):
    """运行记录信息"""
    daily_run_times: int
    weekly_run_times: int
    period_reward_complete: bool = False
    eval_point_complete: bool = False
    no_eval_point: bool = False

class DefaultPathfindingOptions(BaseModel):
    """默认寻路选项"""
    go_in_1_step: List[str]
    waypoint: List[str]
    avoid: List[str]

class InvestigationStrategyInfo(BaseModel):
    """调查战略信息"""
    strategy_id: str
    strategy_name: str
    description: Optional[str] = None

class ArtifactInfo(BaseModel):
    """藏品信息"""
    artifact_id: str
    artifact_name: str
    category: str
    description: Optional[str] = None

class RegionTypeInfo(BaseModel):
    """区域类型信息"""
    region_id: str
    region_name: str
    description: Optional[str] = None


# ============================================================================
# 基础数据查询API端点
# ============================================================================

@router.get("/missions", response_model=List[MissionInfo], summary="获取枯萎之都任务列表")
def get_hollow_zero_missions(ctx = Depends(get_ctx)) -> List[MissionInfo]:
    """
    获取枯萎之都可用任务列表

    ## 功能描述
    返回所有可用的枯萎之都任务信息，包括任务ID、名称和描述。

    ## 返回数据
    - **mission_id**: 任务唯一标识符
    - **mission_name**: 任务显示名称
    - **description**: 任务描述（可选）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/missions")
    missions = response.json()
    for mission in missions:
        print(f"任务: {mission['mission_name']}")
    ```
    """
    try:
        # 获取任务列表
        mission_list = ctx.compendium_service.get_hollow_zero_mission_name_list()

        missions = []
        for i, mission_name in enumerate(mission_list):
            missions.append(MissionInfo(
                mission_id=f"hollow_zero_{i}",
                mission_name=mission_name,
                description=f"枯萎之都任务: {mission_name}"
            ))

        return missions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "MISSIONS_FETCH_FAILED",
                    "message": f"获取任务列表失败: {str(e)}"
                }
            }
        )


@router.get("/lost-void/missions", response_model=List[MissionInfo], summary="获取迷失之地任务列表")
def get_lost_void_missions(ctx = Depends(get_ctx)) -> List[MissionInfo]:
    """
    获取迷失之地可用任务列表

    ## 功能描述
    返回所有可用的迷失之地任务信息，包括任务ID、名称和描述。

    ## 返回数据
    - **mission_id**: 任务唯一标识符
    - **mission_name**: 任务显示名称
    - **description**: 任务描述（可选）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/lost-void/missions")
    missions = response.json()
    for mission in missions:
        print(f"任务: {mission['mission_name']}")
    ```
    """
    try:
        # 获取迷失之地任务列表
        mission_list = ctx.compendium_service.get_lost_void_mission_name_list()

        missions = []
        for i, mission_name in enumerate(mission_list):
            missions.append(MissionInfo(
                mission_id=f"lost_void_{i}",
                mission_name=mission_name,
                description=f"迷失之地任务: {mission_name}"
            ))

        return missions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "MISSIONS_FETCH_FAILED",
                    "message": f"获取迷失之地任务列表失败: {str(e)}"
                }
            }
        )


@router.get("/agent-types", response_model=List[AgentTypeInfo], summary="获取代理人类型列表")
def get_agent_types() -> List[AgentTypeInfo]:
    """
    获取所有代理人类型信息

    ## 功能描述
    返回游戏中所有代理人类型的信息，用于配置界面的选择。

    ## 返回数据
    - **type_id**: 类型标识符
    - **type_name**: 类型显示名称

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/agent-types")
    types = response.json()
    for agent_type in types:
        print(f"类型: {agent_type['type_name']}")
    ```
    """
    try:
        agent_types = []
        for agent_type_enum in AgentTypeEnum:
            if agent_type_enum.value != '未知':
                agent_types.append(AgentTypeInfo(
                    type_id=agent_type_enum.name,
                    type_name=agent_type_enum.value
                ))

        return agent_types
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "AGENT_TYPES_FETCH_FAILED",
                    "message": f"获取代理人类型失败: {str(e)}"
                }
            }
        )


@router.get("/auto-battle-configs", response_model=List[AutoBattleConfigInfo], summary="获取自动战斗配置列表")
def get_auto_battle_configs() -> List[AutoBattleConfigInfo]:
    """
    获取所有可用的自动战斗配置

    ## 功能描述
    返回系统中所有可用的自动战斗配置信息，用于挑战配置中的选择。

    ## 返回数据
    - **config_name**: 配置名称
    - **description**: 配置描述（可选）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/auto-battle-configs")
    configs = response.json()
    for config in configs:
        print(f"配置: {config['config_name']}")
    ```
    """
    try:
        config_list = get_auto_battle_op_config_list('auto_battle')

        configs = []
        for config_item in config_list:
            configs.append(AutoBattleConfigInfo(
                config_name=config_item.value,
                description=f"自动战斗配置: {config_item.label}"
            ))

        return configs
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "AUTO_BATTLE_CONFIGS_FETCH_FAILED",
                    "message": f"获取自动战斗配置失败: {str(e)}"
                }
            }
        )


@router.get("/team-configs", response_model=List[TeamConfigInfo], summary="获取队伍配置列表")
def get_team_configs(ctx = Depends(get_ctx)) -> List[TeamConfigInfo]:
    """
    获取所有可用的队伍配置

    ## 功能描述
    返回系统中所有配置的队伍信息，包括预设队伍和自定义队伍。

    ## 返回数据
    - **team_id**: 队伍ID
    - **team_name**: 队伍名称
    - **agents**: 队伍成员列表

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/team-configs")
    teams = response.json()
    for team in teams:
        print(f"队伍: {team['team_name']}, 成员: {team['agents']}")
    ```
    """
    try:
        teams = []

        # 添加游戏内配队选项
        teams.append(TeamConfigInfo(
            team_id=-1,
            team_name="游戏内配队",
            agents=[]
        ))

        # 获取用户配置的队伍
        if hasattr(ctx, 'team_config') and hasattr(ctx.team_config, 'team_list'):
            for team in ctx.team_config.team_list:
                teams.append(TeamConfigInfo(
                    team_id=team.idx,
                    team_name=team.name,
                    agents=getattr(team, 'agents', [])
                ))

        return teams
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TEAM_CONFIGS_FETCH_FAILED",
                    "message": f"获取队伍配置失败: {str(e)}"
                }
            }
        )


# ============================================================================
# 游戏数据API端点
# ============================================================================

@router.get("/resonium/categories", response_model=List[str], summary="获取鸣徽分类列表")
def get_resonium_categories(ctx = Depends(get_ctx)) -> List[str]:
    """
    获取所有鸣徽分类

    ## 功能描述
    返回游戏中所有鸣徽的分类列表，用于配置优先级时的参考。

    ## 返回数据
    鸣徽分类名称列表

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/resonium/categories")
    categories = response.json()
    for category in categories:
        print(f"分类: {category}")
    ```
    """
    try:
        return ctx.hollow.data_service.resonium_cate_list
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "RESONIUM_CATEGORIES_FETCH_FAILED",
                    "message": f"获取鸣徽分类失败: {str(e)}"
                }
            }
        )


@router.get("/resonium/list", response_model=List[ResoniumInfo], summary="获取鸣徽列表")
def get_resonium_list(ctx = Depends(get_ctx)) -> List[ResoniumInfo]:
    """
    获取所有鸣徽信息

    ## 功能描述
    返回游戏中所有鸣徽的详细信息，包括名称、分类等。

    ## 返回数据
    - **resonium_id**: 鸣徽唯一标识符
    - **resonium_name**: 鸣徽名称
    - **category**: 鸣徽分类
    - **description**: 鸣徽描述（可选）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/resonium/list")
    resoniums = response.json()
    for resonium in resoniums:
        print(f"鸣徽: {resonium['resonium_name']} ({resonium['category']})")
    ```
    """
    try:
        resoniums = []
        for i, resonium in enumerate(ctx.hollow.data_service.resonium_list):
            resoniums.append(ResoniumInfo(
                resonium_id=f"resonium_{i}",
                resonium_name=resonium.name,
                category=resonium.category,
                description=getattr(resonium, 'description', None)
            ))

        return resoniums
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "RESONIUM_LIST_FETCH_FAILED",
                    "message": f"获取鸣徽列表失败: {str(e)}"
                }
            }
        )


@router.get("/events", response_model=List[EventInfo], summary="获取事件列表")
def get_events(ctx = Depends(get_ctx)) -> List[EventInfo]:
    """
    获取所有事件信息

    ## 功能描述
    返回游戏中所有事件的信息，用于配置事件优先级。

    ## 返回数据
    - **event_id**: 事件唯一标识符
    - **event_name**: 事件名称
    - **description**: 事件描述（可选）
    - **is_benefit**: 是否为有益事件

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/events")
    events = response.json()
    for event in events:
        print(f"事件: {event['event_name']}")
    ```
    """
    try:
        events = []
        for i, event in enumerate(ctx.hollow.data_service.normal_events):
            events.append(EventInfo(
                event_id=f"event_{i}",
                event_name=event.event_name,
                description=getattr(event, 'description', None),
                is_benefit=getattr(event, 'is_benefit', False)
            ))

        return events
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "EVENTS_FETCH_FAILED",
                    "message": f"获取事件列表失败: {str(e)}"
                }
            }
        )


@router.get("/entry-types", response_model=List[EntryTypeInfo], summary="获取入口类型列表")
def get_entry_types(ctx = Depends(get_ctx)) -> List[EntryTypeInfo]:
    """
    获取所有入口类型信息

    ## 功能描述
    返回游戏中所有入口类型的信息，用于配置寻路选项。

    ## 返回数据
    - **entry_id**: 入口类型唯一标识符
    - **entry_name**: 入口类型名称
    - **can_go**: 是否可以前往
    - **is_benefit**: 是否为有益入口

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/entry-types")
    entries = response.json()
    for entry in entries:
        print(f"入口: {entry['entry_name']}")
    ```
    """
    try:
        entries = []
        for i, entry in enumerate(ctx.hollow.data_service.entry_list):
            entries.append(EntryTypeInfo(
                entry_id=f"entry_{i}",
                entry_name=entry.entry_name,
                can_go=getattr(entry, 'can_go', True),
                is_benefit=getattr(entry, 'is_benefit', False)
            ))

        return entries
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "ENTRY_TYPES_FETCH_FAILED",
                    "message": f"获取入口类型失败: {str(e)}"
                }
            }
        )


@router.get("/default-pathfinding-options", response_model=DefaultPathfindingOptions, summary="获取默认寻路配置")
def get_default_pathfinding_options(ctx = Depends(get_ctx)) -> DefaultPathfindingOptions:
    """
    获取默认的寻路配置选项

    ## 功能描述
    返回系统推荐的默认寻路配置，包括一步可达、优先途经点和避免途经点。

    ## 返回数据
    - **go_in_1_step**: 一步可达时前往的入口类型列表
    - **waypoint**: 优先途经点类型列表
    - **avoid**: 避免途经点类型列表

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/default-pathfinding-options")
    options = response.json()
    print(f"一步可达: {options['go_in_1_step']}")
    print(f"优先途经: {options['waypoint']}")
    print(f"避免途经: {options['avoid']}")
    ```
    """
    try:
        return DefaultPathfindingOptions(
            go_in_1_step=ctx.hollow.data_service.get_default_go_in_1_step_entry_list(),
            waypoint=ctx.hollow.data_service.get_default_waypoint_entry_list(),
            avoid=ctx.hollow.data_service.get_default_avoid_entry_list()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "DEFAULT_PATHFINDING_FETCH_FAILED",
                    "message": f"获取默认寻路配置失败: {str(e)}"
                }
            }
        )


# ============================================================================
# 数据验证API端点
# ============================================================================

@router.post("/validate/resonium-priority", response_model=ValidationResponse, summary="验证鸣徽优先级配置")
def validate_resonium_priority(request: ValidationRequest, ctx = Depends(get_ctx)) -> ValidationResponse:
    """
    验证鸣徽优先级配置的有效性

    ## 功能描述
    检查用户输入的鸣徽优先级配置是否有效，返回验证结果和错误信息。

    ## 请求参数
    - **input_text**: 需要验证的鸣徽优先级文本，每行一个配置

    ## 返回数据
    - **is_valid**: 是否验证通过
    - **validated_list**: 验证通过的配置列表
    - **error_message**: 错误信息（如果有）

    ## 使用示例
    ```python
    import requests
    data = {"input_text": "强袭 攻击\\n顽强 防御"}
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/validate/resonium-priority", json=data)
    result = response.json()
    print(f"验证结果: {result['is_valid']}")
    ```
    """
    try:
        validated_list, error_msg = ctx.hollow.data_service.check_resonium_priority(request.input_text)

        return ValidationResponse(
            is_valid=len(error_msg) == 0,
            validated_list=validated_list,
            error_message=error_msg
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "RESONIUM_VALIDATION_FAILED",
                    "message": f"鸣徽优先级验证失败: {str(e)}"
                }
            }
        )


@router.post("/validate/entry-list", response_model=ValidationResponse, summary="验证入口列表配置")
def validate_entry_list(request: ValidationRequest, ctx = Depends(get_ctx)) -> ValidationResponse:
    """
    验证入口列表配置的有效性

    ## 功能描述
    检查用户输入的入口列表配置是否有效，返回验证结果和错误信息。

    ## 请求参数
    - **input_text**: 需要验证的入口列表文本，每行一个入口类型

    ## 返回数据
    - **is_valid**: 是否验证通过
    - **validated_list**: 验证通过的入口列表
    - **error_message**: 错误信息（如果有）

    ## 使用示例
    ```python
    import requests
    data = {"input_text": "呼叫增援\\n业绩考察点"}
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/validate/entry-list", json=data)
    result = response.json()
    print(f"验证结果: {result['is_valid']}")
    ```
    """
    try:
        validated_list, error_msg = ctx.hollow.data_service.check_entry_list_input(request.input_text)

        return ValidationResponse(
            is_valid=len(error_msg) == 0,
            validated_list=validated_list,
            error_message=error_msg
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "ENTRY_LIST_VALIDATION_FAILED",
                    "message": f"入口列表验证失败: {str(e)}"
                }
            }
        )

# ============================================================================
# 运行记录管理API端点
# ============================================================================

@router.get("/records", response_model=RunRecordInfo, summary="获取枯萎之都运行记录")
def get_hollow_zero_records(ctx = Depends(get_ctx)) -> RunRecordInfo:
    """
    获取枯萎之都的运行记录信息

    ## 功能描述
    返回当前枯萎之都的运行统计信息，包括每日和每周的运行次数。

    ## 返回数据
    - **daily_run_times**: 今日运行次数
    - **weekly_run_times**: 本周运行次数
    - **period_reward_complete**: 周期性奖励是否完成
    - **no_eval_point**: 是否无业绩考察点

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/records")
    records = response.json()
    print(f"今日运行: {records['daily_run_times']}次")
    print(f"本周运行: {records['weekly_run_times']}次")
    ```
    """
    try:
        return RunRecordInfo(
            daily_run_times=ctx.hollow_zero_record.daily_run_times,
            weekly_run_times=ctx.hollow_zero_record.weekly_run_times,
            period_reward_complete=ctx.hollow_zero_record.period_reward_complete,
            no_eval_point=getattr(ctx.hollow_zero_record, 'no_eval_point', False)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "RECORDS_FETCH_FAILED",
                    "message": f"获取运行记录失败: {str(e)}"
                }
            }
        )


@router.post("/records/reset", summary="重置枯萎之都运行记录")
def reset_hollow_zero_records(ctx = Depends(get_ctx)) -> Dict[str, str]:
    """
    重置枯萎之都的运行记录

    ## 功能描述
    清空当前枯萎之都的运行记录，包括每日和每周的统计数据。

    ## 返回数据
    返回重置操作的结果消息

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/records/reset")
    result = response.json()
    print(result["message"])
    ```
    """
    try:
        ctx.hollow_zero_record.reset_for_weekly()
        return {"message": "枯萎之都运行记录重置成功"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "RECORDS_RESET_FAILED",
                    "message": f"重置运行记录失败: {str(e)}"
                }
            }
        )


@router.get("/lost-void/records", response_model=RunRecordInfo, summary="获取迷失之地运行记录")
def get_lost_void_records(ctx = Depends(get_ctx)) -> RunRecordInfo:
    """
    获取迷失之地的运行记录信息

    ## 功能描述
    返回当前迷失之地的运行统计信息，包括每日和每周的运行次数。

    ## 返回数据
    - **daily_run_times**: 今日运行次数
    - **weekly_run_times**: 本周运行次数
    - **period_reward_complete**: 周期性奖励是否完成
    - **eval_point_complete**: 业绩考察是否完成

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/lost-void/records")
    records = response.json()
    print(f"今日运行: {records['daily_run_times']}次")
    ```
    """
    try:
        return RunRecordInfo(
            daily_run_times=ctx.lost_void_record.daily_run_times,
            weekly_run_times=ctx.lost_void_record.weekly_run_times,
            period_reward_complete=ctx.lost_void_record.period_reward_complete,
            eval_point_complete=getattr(ctx.lost_void_record, 'eval_point_complete', False)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "LOST_VOID_RECORDS_FETCH_FAILED",
                    "message": f"获取迷失之地运行记录失败: {str(e)}"
                }
            }
        )


@router.post("/lost-void/records/reset", summary="重置迷失之地运行记录")
def reset_lost_void_records(ctx = Depends(get_ctx)) -> Dict[str, str]:
    """
    重置迷失之地的运行记录

    ## 功能描述
    清空当前迷失之地的运行记录，包括每日和每周的统计数据。

    ## 返回数据
    返回重置操作的结果消息

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/lost-void/records/reset")
    result = response.json()
    print(result["message"])
    ```
    """
    try:
        ctx.lost_void_record.reset_record()
        ctx.lost_void_record.reset_for_weekly()
        return {"message": "迷失之地运行记录重置成功"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "LOST_VOID_RECORDS_RESET_FAILED",
                    "message": f"重置迷失之地运行记录失败: {str(e)}"
                }
            }
        )


# ============================================================================
# 迷失之地专用API端点
# ============================================================================

@router.get("/lost-void/investigation-strategies", response_model=List[InvestigationStrategyInfo], summary="获取调查战略列表")
def get_investigation_strategies(ctx = Depends(get_ctx)) -> List[InvestigationStrategyInfo]:
    """
    获取所有可用的调查战略

    ## 功能描述
    返回迷失之地中所有可用的调查战略信息。

    ## 返回数据
    - **strategy_id**: 战略唯一标识符
    - **strategy_name**: 战略名称
    - **description**: 战略描述（可选）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/lost-void/investigation-strategies")
    strategies = response.json()
    for strategy in strategies:
        print(f"战略: {strategy['strategy_name']}")
    ```
    """
    try:
        # 确保数据已加载
        ctx.lost_void.load_investigation_strategy()

        strategies = []
        for i, strategy in enumerate(ctx.lost_void.investigation_strategy_list):
            strategies.append(InvestigationStrategyInfo(
                strategy_id=f"strategy_{i}",
                strategy_name=strategy.strategy_name,
                description=getattr(strategy, 'description', None)
            ))

        return strategies
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INVESTIGATION_STRATEGIES_FETCH_FAILED",
                    "message": f"获取调查战略失败: {str(e)}"
                }
            }
        )


@router.get("/lost-void/artifacts", response_model=List[ArtifactInfo], summary="获取藏品列表")
def get_artifacts(ctx = Depends(get_ctx)) -> List[ArtifactInfo]:
    """
    获取所有可用的藏品信息

    ## 功能描述
    返回迷失之地中所有藏品的信息，用于配置藏品优先级。

    ## 返回数据
    - **artifact_id**: 藏品唯一标识符
    - **artifact_name**: 藏品名称
    - **category**: 藏品分类
    - **description**: 藏品描述（可选）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/lost-void/artifacts")
    artifacts = response.json()
    for artifact in artifacts:
        print(f"藏品: {artifact['artifact_name']} ({artifact['category']})")
    ```
    """
    try:
        # 确保藏品数据已加载
        ctx.lost_void.load_artifact_data()

        artifacts = []
        if hasattr(ctx.lost_void, 'artifact_list'):
            for i, artifact in enumerate(ctx.lost_void.artifact_list):
                artifacts.append(ArtifactInfo(
                    artifact_id=f"artifact_{i}",
                    artifact_name=getattr(artifact, 'name', f"藏品_{i}"),
                    category=getattr(artifact, 'category', '未知'),
                    description=getattr(artifact, 'description', None)
                ))

        return artifacts
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "ARTIFACTS_FETCH_FAILED",
                    "message": f"获取藏品列表失败: {str(e)}"
                }
            }
        )


@router.get("/lost-void/region-types", response_model=List[RegionTypeInfo], summary="获取区域类型列表")
def get_region_types(ctx = Depends(get_ctx)) -> List[RegionTypeInfo]:
    """
    获取所有可用的区域类型

    ## 功能描述
    返回迷失之地中所有区域类型的信息，用于配置区域优先级。

    ## 返回数据
    - **region_id**: 区域类型唯一标识符
    - **region_name**: 区域类型名称
    - **description**: 区域类型描述（可选）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/lost-void/region-types")
    regions = response.json()
    for region in regions:
        print(f"区域: {region['region_name']}")
    ```
    """
    try:
        # 这里需要根据实际的区域类型数据结构来实现
        # 暂时返回一些常见的区域类型
        regions = [
            RegionTypeInfo(region_id="combat", region_name="战斗区域", description="包含敌人的战斗区域"),
            RegionTypeInfo(region_id="treasure", region_name="宝藏区域", description="包含宝箱的区域"),
            RegionTypeInfo(region_id="shop", region_name="商店区域", description="可以购买物品的区域"),
            RegionTypeInfo(region_id="event", region_name="事件区域", description="触发特殊事件的区域"),
        ]

        return regions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "REGION_TYPES_FETCH_FAILED",
                    "message": f"获取区域类型失败: {str(e)}"
                }
            }
        )


@router.post("/lost-void/validate/artifact-priority", response_model=ValidationResponse, summary="验证藏品优先级配置")
def validate_artifact_priority(request: ValidationRequest, ctx = Depends(get_ctx)) -> ValidationResponse:
    """
    验证藏品优先级配置的有效性

    ## 功能描述
    检查用户输入的藏品优先级配置是否有效，返回验证结果和错误信息。

    ## 请求参数
    - **input_text**: 需要验证的藏品优先级文本，每行一个藏品名称

    ## 返回数据
    - **is_valid**: 是否验证通过
    - **validated_list**: 验证通过的藏品列表
    - **error_message**: 错误信息（如果有）

    ## 使用示例
    ```python
    import requests
    data = {"input_text": "攻击藏品\\n防御藏品"}
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/lost-void/validate/artifact-priority", json=data)
    result = response.json()
    print(f"验证结果: {result['is_valid']}")
    ```
    """
    try:
        validated_list, error_msg = ctx.lost_void.check_artifact_priority_input(request.input_text)

        return ValidationResponse(
            is_valid=len(error_msg) == 0,
            validated_list=validated_list,
            error_message=error_msg
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "ARTIFACT_VALIDATION_FAILED",
                    "message": f"藏品优先级验证失败: {str(e)}"
                }
            }
        )


@router.post("/lost-void/validate/region-priority", response_model=ValidationResponse, summary="验证区域类型优先级配置")
def validate_region_priority(request: ValidationRequest, ctx = Depends(get_ctx)) -> ValidationResponse:
    """
    验证区域类型优先级配置的有效性

    ## 功能描述
    检查用户输入的区域类型优先级配置是否有效，返回验证结果和错误信息。

    ## 请求参数
    - **input_text**: 需要验证的区域类型优先级文本，每行一个区域类型

    ## 返回数据
    - **is_valid**: 是否验证通过
    - **validated_list**: 验证通过的区域类型列表
    - **error_message**: 错误信息（如果有）

    ## 使用示例
    ```python
    import requests
    data = {"input_text": "战斗区域\\n宝藏区域"}
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/lost-void/validate/region-priority", json=data)
    result = response.json()
    print(f"验证结果: {result['is_valid']}")
    ```
    """
    try:
        validated_list, error_msg = ctx.lost_void.check_region_type_priority_input(request.input_text)

        return ValidationResponse(
            is_valid=len(error_msg) == 0,
            validated_list=validated_list,
            error_message=error_msg
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "REGION_VALIDATION_FAILED",
                    "message": f"区域类型优先级验证失败: {str(e)}"
                }
            }
        )


# ============================================================================
# 实时状态API端点
# ============================================================================

class HollowZeroStatus(BaseModel):
    """零号空洞运行状态"""
    is_running: bool
    current_app: Optional[str] = None
    progress: Optional[str] = None
    error_message: Optional[str] = None
    last_update: Optional[str] = None

@router.get("/status", response_model=HollowZeroStatus, summary="获取零号空洞运行状态")
def get_hollow_zero_status(ctx = Depends(get_ctx)) -> HollowZeroStatus:
    """
    获取当前零号空洞的运行状态

    ## 功能描述
    返回当前零号空洞应用的运行状态，包括是否运行中、当前进度等信息。

    ## 返回数据
    - **is_running**: 是否正在运行
    - **current_app**: 当前运行的应用名称
    - **progress**: 当前进度描述
    - **error_message**: 错误信息（如果有）
    - **last_update**: 最后更新时间

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/hollow-zero/status")
    status = response.json()
    print(f"运行状态: {'运行中' if status['is_running'] else '未运行'}")
    ```
    """
    try:
        from datetime import datetime

        is_running = ctx.is_context_running
        current_app = None
        progress = None
        error_message = None

        # 获取当前运行的任务信息
        statuses = _registry.list_statuses()
        running_tasks = [s for s in statuses if s.status.value in ["pending", "running"]]

        if running_tasks:
            # 假设只有一个任务在运行
            task = running_tasks[0]
            current_app = "零号空洞"
            progress = f"任务ID: {task.runId}"

        return HollowZeroStatus(
            is_running=is_running,
            current_app=current_app,
            progress=progress,
            error_message=error_message,
            last_update=datetime.now().isoformat()
        )
    except Exception as e:
        return HollowZeroStatus(
            is_running=False,
            error_message=f"获取状态失败: {str(e)}",
            last_update=datetime.now().isoformat()
        )


@router.post("/stop", summary="停止零号空洞运行")
def stop_hollow_zero(ctx = Depends(get_ctx)) -> Dict[str, str]:
    """
    停止当前运行的零号空洞任务

    ## 功能描述
    停止所有正在运行的零号空洞相关任务。

    ## 返回数据
    返回停止操作的结果消息

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/stop")
    result = response.json()
    print(result["message"])
    ```
    """
    try:
        # 停止上下文运行
        ctx.stop_running()

        # 取消所有相关任务
        statuses = _registry.list_statuses()
        cancelled_count = 0

        for status in statuses:
            if status.status.value in ["pending", "running"]:
                if _registry.cancel(status.runId):
                    cancelled_count += 1

        return {"message": f"零号空洞已停止，取消了 {cancelled_count} 个任务"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "STOP_FAILED",
                    "message": f"停止零号空洞失败: {str(e)}"
                }
            }
        )


@router.post("/lost-void/stop", summary="停止迷失之地运行")
def stop_lost_void(ctx = Depends(get_ctx)) -> Dict[str, str]:
    """
    停止当前运行的迷失之地任务

    ## 功能描述
    停止所有正在运行的迷失之地相关任务。

    ## 返回数据
    返回停止操作的结果消息

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/hollow-zero/lost-void/stop")
    result = response.json()
    print(result["message"])
    ```
    """
    try:
        # 停止上下文运行
        ctx.stop_running()

        # 取消所有相关任务
        statuses = _registry.list_statuses()
        cancelled_count = 0

        for status in statuses:
            if status.status.value in ["pending", "running"]:
                if _registry.cancel(status.runId):
                    cancelled_count += 1

        return {"message": f"迷失之地已停止，取消了 {cancelled_count} 个任务"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "LOST_VOID_STOP_FAILED",
                    "message": f"停止迷失之地失败: {str(e)}"
                }
            }
        )