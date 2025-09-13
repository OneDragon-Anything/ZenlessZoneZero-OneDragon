from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from zzz_od.api.deps import get_ctx  # Corrected: was get_context
from zzz_od.context.zzz_context import ZContext

router = APIRouter(
    prefix="/api/v1/battle-assistant",
    tags=["Battle Assistant"],
)


class AutoBattleConfig(BaseModel):
    """自动战斗配置"""
    enabled: bool
    script_id: str
    # 可以根据实际需要添加更多配置项
    # e.g., use_skills: bool, burst_threshold: int


class DodgeAssistantConfig(BaseModel):
    """闪避助手配置"""
    enabled: bool
    mode: str  # e.g., "auto", "manual"


class BattleState(BaseModel):
    """战斗状态"""
    is_in_battle: bool
    current_script: Optional[str]
    enemies_detected: int


@router.get("/auto-battle/config", response_model=AutoBattleConfig, summary="获取自动战斗配置")
def get_auto_battle_config(ctx: ZContext = Depends(get_ctx)):
    """
    获取当前自动战斗的配置
    """
    # TODO: 请在 ZContext 中实现 battle_assistant_config 属性
    # 示例:
    # return AutoBattleConfig(
    #     enabled=ctx.battle_assistant_config.auto_battle_enabled,
    #     script_id=ctx.battle_assistant_config.auto_battle_script_id
    # )
    return AutoBattleConfig(enabled=False, script_id="default")


@router.post("/auto-battle/config", summary="更新自动战斗配置")
def update_auto_battle_config(config: AutoBattleConfig, ctx: ZContext = Depends(get_ctx)):
    """
    更新自动战斗的配置
    """
    # TODO: 请在 ZContext 中实现 battle_assistant_config 属性并保存
    # 示例:
    # ctx.battle_assistant_config.auto_battle_enabled = config.enabled
    # ctx.battle_assistant_config.auto_battle_script_id = config.script_id
    # ctx.battle_assistant_config.save()
    return {"msg": "Auto battle config updated successfully"}


@router.post("/auto-battle/start", summary="启动自动战斗")
def start_auto_battle(ctx: ZContext = Depends(get_ctx)):
    """
    启动自动战斗流程
    """
    # TODO: 调用启动自动战斗的业务逻辑
    # ctx.battle_service.start_auto_battle()
    return {"msg": "Auto battle started"}


@router.post("/auto-battle/stop", summary="停止自动战斗")
def stop_auto_battle(ctx: ZContext = Depends(get_ctx)):
    """
    停止自动战斗流程
    """
    # TODO: 调用停止自动战斗的业务逻辑
    # ctx.battle_service.stop_auto_battle()
    return {"msg": "Auto battle stopped"}


@router.get("/dodge-assistant/config", response_model=DodgeAssistantConfig, summary="获取闪避助手配置")
def get_dodge_assistant_config(ctx: ZContext = Depends(get_ctx)):
    """
    获取当前闪避助手的配置
    """
    # TODO: 请在 ZContext 中实现 battle_assistant_config 属性
    # 示例:
    # return DodgeAssistantConfig(
    #     enabled=ctx.battle_assistant_config.dodge_assistant_enabled,
    #     mode=ctx.battle_assistant_config.dodge_assistant_mode
    # )
    return DodgeAssistantConfig(enabled=False, mode="auto")


@router.post("/dodge-assistant/config", summary="更新闪避助手配置")
def update_dodge_assistant_config(config: DodgeAssistantConfig, ctx: ZContext = Depends(get_ctx)):
    """
    更新闪避助手的配置
    """
    # TODO: 请在 ZContext 中实现 battle_assistant_config 属性并保存
    # 示例:
    # ctx.battle_assistant_config.dodge_assistant_enabled = config.enabled
    # ctx.battle_assistant_config.dodge_assistant_mode = config.mode
    # ctx.battle_assistant_config.save()
    return {"msg": "Dodge assistant config updated successfully"}


@router.get("/state", response_model=BattleState, summary="获取实时战斗状态")
def get_battle_state(ctx: ZContext = Depends(get_ctx)):
    """
    获取当前的战斗状态，用于UI展示
    建议前端通过轮询或WebSocket来调用此接口
    """
    # TODO: 请在 ZContext 中实现 battle_state 属性
    # 示例:
    # return BattleState(
    #     is_in_battle=ctx.battle_state.is_in_battle,
    #     current_script=ctx.battle_state.current_script,
    #     enemies_detected=ctx.battle_state.enemies_detected
    # )
    return BattleState(is_in_battle=False, current_script=None, enemies_detected=0)

# 可以在这里继续添加 自动战斗脚本编辑器(CRUD)、操作调试、模板生成等API
