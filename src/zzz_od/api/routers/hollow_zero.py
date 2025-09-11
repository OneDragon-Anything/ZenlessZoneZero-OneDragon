from __future__ import annotations

from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from zzz_od.api.deps import get_ctx
from zzz_od.api.models import RunIdResponse
from zzz_od.api.security import get_api_key_dependency
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.bridges import attach_run_event_bridge
from zzz_od.hollow_zero.hollow_zero_challenge_config import HollowZeroChallengeConfig, get_all_hollow_zero_challenge_config, get_hollow_zero_challenge_new_name, HollowZeroChallengePathFinding
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import LostVoidChallengeConfig, get_all_lost_void_challenge_config, get_lost_void_challenge_new_name, LostVoidPeriodBuffNo


router = APIRouter(
    prefix="/api/v1/hollow-zero",
    tags=["hollow-zero"],
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


@router.post("/run")
async def run_hollow_zero():
    """运行零号空洞 - 枯萎之都"""
    run_id = _run_via_onedragon_with_temp(["hollow_zero"])
    return RunIdResponse(runId=run_id)


@router.post("/lost-void/run")
async def run_lost_void():
    """运行零号空洞 - 迷失之地"""
    run_id = _run_via_onedragon_with_temp(["lost_void"])
    return RunIdResponse(runId=run_id)


# -------- Hollow Zero Challenge Config --------


@router.get("/challenge-configs")
def get_hollow_zero_challenge_configs() -> List[Dict[str, Any]]:
    """获取所有枯萎之都挑战配置"""
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


@router.get("/challenge-configs/{module_name}")
def get_hollow_zero_challenge_config(module_name: str) -> Dict[str, Any]:
    """获取指定的枯萎之都挑战配置"""
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


@router.post("/challenge-configs")
def create_hollow_zero_challenge_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """创建新的枯萎之都挑战配置"""
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


@router.put("/challenge-configs/{module_name}")
def update_hollow_zero_challenge_config(module_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新指定的枯萎之都挑战配置"""
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


@router.delete("/challenge-configs/{module_name}")
def delete_hollow_zero_challenge_config(module_name: str) -> Dict[str, Any]:
    """删除指定的枯萎之都挑战配置"""
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


@router.get("/lost-void/challenge-configs")
def get_lost_void_challenge_configs() -> List[Dict[str, Any]]:
    """获取所有迷失之地挑战配置"""
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


@router.get("/lost-void/challenge-configs/{module_name}")
def get_lost_void_challenge_config(module_name: str) -> Dict[str, Any]:
    """获取指定的迷失之地挑战配置"""
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


@router.post("/lost-void/challenge-configs")
def create_lost_void_challenge_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """创建新的迷失之地挑战配置"""
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


@router.put("/lost-void/challenge-configs/{module_name}")
def update_lost_void_challenge_config(module_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新指定的迷失之地挑战配置"""
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


@router.delete("/lost-void/challenge-configs/{module_name}")
def delete_lost_void_challenge_config(module_name: str) -> Dict[str, Any]:
    """删除指定的迷失之地挑战配置"""
    configs = get_all_lost_void_challenge_config()
    config = next((c for c in configs if c.module_name == module_name), None)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    # 删除配置文件
    import os
    if os.path.exists(config.file_path):
        os.remove(config.file_path)

    return {"message": "Configuration deleted successfully"}
