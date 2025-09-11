from __future__ import annotations

from typing import Dict, Any

from fastapi import APIRouter, Depends

from zzz_od.api.deps import get_ctx
from zzz_od.api.models import RunIdResponse
from zzz_od.api.security import get_api_key_dependency
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.bridges import attach_run_event_bridge
from zzz_od.application.commission_assistant.commission_assistant_app import CommissionAssistantApp
from zzz_od.application.life_on_line.life_on_line_app import LifeOnLineApp
from zzz_od.application.game_config_checker.mouse_sensitivity_checker import MouseSensitivityChecker
from zzz_od.application.game_config_checker.predefined_team_checker import PredefinedTeamChecker


router = APIRouter(
    prefix="/api/v1/game-assistant",
    tags=["game-assistant"],
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


# -------- Commission Assistant (委托助手) --------


@router.post("/commission-assistant/run")
async def run_commission_assistant():
    """运行委托助手"""
    run_id = _run_via_onedragon_with_temp(["commission_assistant"])
    return RunIdResponse(runId=run_id)


@router.get("/commission-assistant/config")
def get_commission_assistant_config() -> Dict[str, Any]:
    """获取委托助手配置"""
    ctx = get_ctx()
    config = ctx.commission_assistant_config
    return {
        "dialogClickInterval": config.dialog_click_interval,
        "storyMode": config.story_mode,
        "dialogOption": config.dialog_option,
        "dodgeConfig": config.dodge_config,
        "dodgeSwitch": config.dodge_switch,
        "autoBattle": config.auto_battle,
        "autoBattleSwitch": config.auto_battle_switch,
    }


@router.put("/commission-assistant/config")
def update_commission_assistant_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新委托助手配置"""
    ctx = get_ctx()
    config = ctx.commission_assistant_config

    if "dialogClickInterval" in payload:
        config.dialog_click_interval = float(payload["dialogClickInterval"])
    if "storyMode" in payload:
        config.story_mode = payload["storyMode"]
    if "dialogOption" in payload:
        config.dialog_option = payload["dialogOption"]
    if "dodgeConfig" in payload:
        config.dodge_config = payload["dodgeConfig"]
    if "dodgeSwitch" in payload:
        config.dodge_switch = payload["dodgeSwitch"]
    if "autoBattle" in payload:
        config.auto_battle = payload["autoBattle"]
    if "autoBattleSwitch" in payload:
        config.auto_battle_switch = payload["autoBattleSwitch"]

    return {"message": "Configuration updated successfully"}


# -------- Life on Line (拿命验收) --------


@router.post("/life-on-line/run")
async def run_life_on_line():
    """运行拿命验收"""
    run_id = _run_via_onedragon_with_temp(["life_on_line"])
    return RunIdResponse(runId=run_id)


@router.get("/life-on-line/config")
def get_life_on_line_config() -> Dict[str, Any]:
    """获取拿命验收配置"""
    ctx = get_ctx()
    config = ctx.life_on_line_config
    return {
        "dailyPlanTimes": config.daily_plan_times,
        "predefinedTeamIdx": config.predefined_team_idx,
    }


@router.put("/life-on-line/config")
def update_life_on_line_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """更新拿命验收配置"""
    ctx = get_ctx()
    config = ctx.life_on_line_config

    if "dailyPlanTimes" in payload:
        config.daily_plan_times = int(payload["dailyPlanTimes"])
    if "predefinedTeamIdx" in payload:
        config.predefined_team_idx = int(payload["predefinedTeamIdx"])

    return {"message": "Configuration updated successfully"}


@router.get("/life-on-line/record")
def get_life_on_line_record() -> Dict[str, Any]:
    """获取拿命验收运行记录"""
    ctx = get_ctx()
    record = ctx.life_on_line_record
    return {
        "dailyRunTimes": record.daily_run_times,
        "isFinishedByTimes": record.is_finished_by_times,
    }


# -------- Mouse Sensitivity Checker (鼠标校准) --------


@router.post("/mouse-sensitivity-checker/run")
async def run_mouse_sensitivity_checker():
    """运行鼠标灵敏度检查器"""
    run_id = _run_via_onedragon_with_temp(["mouse_sensitivity_checker"])
    return RunIdResponse(runId=run_id)


# -------- Predefined Team Checker (预备编队识别) --------


@router.post("/predefined-team-checker/run")
async def run_predefined_team_checker():
    """运行预设队伍检查器"""
    run_id = _run_via_onedragon_with_temp(["predefined_team_checker"])
    return RunIdResponse(runId=run_id)
