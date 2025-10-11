import os
import asyncio
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from one_dragon.utils.log_utils import log

from zzz_od.api.deps import get_ctx
from zzz_od.api.models import ControlResponse, StatusResponse, LogReplayResponse
from zzz_od.context.zzz_context import ZContext
from zzz_od.api.utils.config_manager import config_manager, template_manager
from zzz_od.api.utils.config_validation import config_validator
from zzz_od.api.battle_assistant_models import (
    DodgeAssistantConfig,
    AutoBattleConfig,
    AutoBattleConfigUpdate,
    ConfigListResponse,
    ConfigInfo,
    DodgeAssistantConfigUpdate,
    OperationDebugConfig,
    OperationDebugConfigUpdate,
    TemplateInfo,
    TemplateListResponse,
    TaskResponse,
    BattleAssistantSettings,
    BattleAssistantSettingsUpdate,
    GamepadTypeInfo,
    GamepadTypesResponse,
    BattleState,
    DetailedBattleState,
    StateRecordInfo,
    TaskInfo,
    BattleAssistantError,
    ConfigurationError,
    FileOperationError,
    TaskExecutionError
)
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.bridges import attach_run_event_bridge, attach_battle_assistant_event_bridge, BattleAssistantEventType, broadcast_battle_assistant_event
from zzz_od.api.status_builder import build_onedragon_aggregate
from zzz_od.config.game_config import GamepadTypeEnum

# 全局注册表
_registry = get_global_run_registry()


def _normalize_gamepad_type(gamepad_type: str) -> str:
    """将显示名称转换为实际的枚举值"""
    if gamepad_type == "无手柄":
        return "none"
    elif gamepad_type == "Xbox手柄":
        return "xbox"
    elif gamepad_type == "DS4手柄":
        return "ds4"
    else:
        return gamepad_type  # 如果已经是正确的值，直接返回

def _calc_task_duration(auto_op, running_task, now: float) -> float:
    """根据当前任务所在的handler计算持续时间，未命中时返回0."""
    if auto_op is None or running_task is None:
        return 0.0

    last_trigger_time = getattr(auto_op, 'last_trigger_time', {}) or {}
    handler_key = None

    trigger_name = getattr(running_task, 'trigger', None)
    if trigger_name:
        trigger_handlers = getattr(auto_op, 'trigger_scene_handler', {}) or {}
        handler = trigger_handlers.get(trigger_name)
        if handler is not None:
            handler_key = id(handler)
    else:
        handler = getattr(auto_op, 'normal_scene_handler', None)
        if handler is not None:
            handler_key = id(handler)

    if handler_key is None:
        return 0.0

    trigger_timestamp = last_trigger_time.get(handler_key)
    if trigger_timestamp is None:
        return 0.0

    duration = now - trigger_timestamp
    return duration if duration > 0 else 0.0

router = APIRouter(
    prefix="/api/v1/battle-assistant",
    tags=["战斗助手 Battle Assistant"],
)

_registry = get_global_run_registry()


# ============================================================================
# 自动战斗配置管理API端点
# ============================================================================

@router.get("/auto-battle/config", response_model=AutoBattleConfig, summary="获取自动战斗配置")
def get_auto_battle_config(ctx: ZContext = Depends(get_ctx)):
    """
    获取当前自动战斗的配置

    ## 功能描述
    返回当前自动战斗的详细配置信息，包括配置名称、GPU使用设置、截图间隔和手柄类型等。

    ## 返回数据
    - **config_name**: 当前使用的配置名称
    - **enabled**: 是否启用自动战斗
    - **use_gpu**: 是否使用GPU加速
    - **screenshot_interval**: 截图间隔时间（秒）
    - **gamepad_type**: 手柄类型设置

    ## 错误码
    - **CONFIG_READ_FAILED**: 读取配置失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/auto-battle/config")
    config = response.json()
    print(f"当前配置: {config['config_name']}")
    ```
    """
    try:
        config_name = ctx.battle_assistant_config.auto_battle_config

        return AutoBattleConfig(
            config_name=config_name,
            enabled=True,  # 默认启用
            use_gpu=ctx.battle_assistant_config.use_gpu,
            screenshot_interval=ctx.battle_assistant_config.screenshot_interval,
            gamepad_type=ctx.battle_assistant_config.gamepad_type
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIG_READ_FAILED",
                    "message": f"读取自动战斗配置失败: {str(e)}"
                }
            }
        )


@router.put("/auto-battle/config", summary="更新自动战斗配置")
def update_auto_battle_config(config: AutoBattleConfigUpdate, ctx: ZContext = Depends(get_ctx)):
    """
    更新自动战斗的配置

    ## 功能描述
    更新自动战斗的配置参数，支持部分更新。只需要提供需要修改的字段。

    ## 请求参数
    - **config_name** (可选): 配置名称
    - **use_gpu** (可选): 是否使用GPU，布尔值
    - **screenshot_interval** (可选): 截图间隔，范围0.01-1.0秒
    - **gamepad_type** (可选): 手柄类型

    ## 响应数据
    返回更新成功的消息

    ## 错误码
    - **CONFIG_UPDATE_FAILED**: 配置更新失败
    - **VALIDATION_ERROR**: 参数验证失败

    ## 使用示例
    ```python
    import requests
    data = {
        "use_gpu": True,
        "screenshot_interval": 0.05
    }
    response = requests.put("http://localhost:8000/api/v1/battle-assistant/auto-battle/config", json=data)
    print(response.json()["message"])
    ```
    """
    try:
        # 更新配置名称（如果提供）
        if config.config_name is not None:
            ctx.battle_assistant_config.auto_battle_config = config.config_name

        # 更新GPU使用设置（如果提供）
        if config.use_gpu is not None:
            ctx.battle_assistant_config.use_gpu = config.use_gpu

        # 更新截图间隔（如果提供）
        if config.screenshot_interval is not None:
            ctx.battle_assistant_config.screenshot_interval = config.screenshot_interval

        # 更新手柄类型（如果提供）
        if config.gamepad_type is not None:
            ctx.battle_assistant_config.gamepad_type = _normalize_gamepad_type(config.gamepad_type)

        # 保存配置
        ctx.battle_assistant_config.save()

        # 广播配置更新事件
        broadcast_battle_assistant_event(
            BattleAssistantEventType.CONFIG_UPDATED,
            {
                "config_type": "auto_battle",
                "config_data": {
                    "config_name": config.config_name,
                    "use_gpu": config.use_gpu,
                    "screenshot_interval": config.screenshot_interval,
                    "gamepad_type": config.gamepad_type
                }
            }
        )

        return {"message": "自动战斗配置更新成功"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIG_UPDATE_FAILED",
                    "message": f"更新自动战斗配置失败: {str(e)}"
                }
            }
        )


@router.get("/auto-battle/configs", response_model=ConfigListResponse, summary="获取自动战斗配置列表")
def get_auto_battle_configs(ctx: ZContext = Depends(get_ctx)):
    """
    获取所有可用的自动战斗配置文件列表

    ## 功能描述
    返回系统中所有可用的自动战斗配置文件列表，包括配置的基本信息和当前使用的配置。

    ## 返回数据
    - **configs**: 配置文件列表
      - **name**: 配置名称
      - **description**: 配置描述
      - **last_modified**: 最后修改时间
      - **file_size**: 文件大小（字节）
    - **current_config**: 当前使用的配置名称

    ## 错误码
    - **CONFIG_LIST_FAILED**: 获取配置列表失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/auto-battle/configs")
    data = response.json()
    print(f"可用配置: {[config['name'] for config in data['configs']]}")
    print(f"当前配置: {data['current_config']}")
    ```
    """
    try:
        # 使用配置管理器获取配置列表
        config_list = config_manager.get_config_list("auto_battle")
        current_config = ctx.battle_assistant_config.auto_battle_config

        configs = []
        for config_info in config_list:
            configs.append(ConfigInfo(
                name=config_info["name"],
                description=config_info["description"],
                last_modified=config_info["last_modified"],
                file_size=config_info["file_size"]
            ))

        return ConfigListResponse(
            configs=configs,
            current_config=current_config
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIG_LIST_FAILED",
                    "message": f"获取自动战斗配置列表失败: {str(e)}"
                }
            }
        )


@router.delete("/auto-battle/configs/{name}", summary="删除自动战斗配置")
def delete_auto_battle_config(name: str, ctx: ZContext = Depends(get_ctx)):
    """
    删除指定的自动战斗配置文件

    ## 功能描述
    删除指定名称的自动战斗配置文件。不能删除当前正在使用的配置和示例配置文件。

    ## 路径参数
    - **name**: 要删除的配置文件名称

    ## 响应数据
    返回删除成功的消息

    ## 错误码
    - **CANNOT_DELETE_CURRENT**: 不能删除当前正在使用的配置
    - **CANNOT_DELETE_SAMPLE**: 不能删除示例配置文件
    - **CONFIG_NOT_FOUND**: 配置文件不存在
    - **CONFIG_DELETE_FAILED**: 删除配置文件失败

    ## 使用示例
    ```python
    import requests
    response = requests.delete("http://localhost:8000/api/v1/battle-assistant/auto-battle/configs/我的配置")
    print(response.json()["message"])
    ```
    """
    try:
        # 检查是否是当前使用的配置
        current_config = ctx.battle_assistant_config.auto_battle_config
        if current_config == name:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "CANNOT_DELETE_CURRENT",
                        "message": "不能删除当前正在使用的配置"
                    }
                }
            )

        # 使用配置管理器删除配置
        success, error_msg = config_manager.delete_config("auto_battle", name, allow_sample_delete=False)

        if not success:
            if "示例配置文件" in error_msg:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "CANNOT_DELETE_SAMPLE",
                            "message": error_msg
                        }
                    }
                )
            elif "不存在" in error_msg:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": {
                            "code": "CONFIG_NOT_FOUND",
                            "message": error_msg
                        }
                    }
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": {
                            "code": "CONFIG_DELETE_FAILED",
                            "message": error_msg
                        }
                    }
                )

        return {"message": f"配置文件 {name} 删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIG_DELETE_FAILED",
                    "message": f"删除配置文件失败: {str(e)}"
                }
            }
        )


# ============================================================================
# 闪避助手API端点
# ============================================================================

@router.get("/dodge/config", response_model=DodgeAssistantConfig, summary="获取闪避助手配置")
def get_dodge_config(ctx: ZContext = Depends(get_ctx)):
    """
    获取当前闪避助手的配置

    ## 功能描述
    返回当前闪避助手的详细配置信息，包括启用状态、闪避方式、敏感度和反应时间等。

    ## 返回数据
    - **enabled**: 是否启用闪避助手
    - **dodge_method**: 闪避方式/配置名称
    - **sensitivity**: 敏感度设置（0.0-1.0）
    - **reaction_time**: 反应时间（秒）

    ## 错误码
    - **CONFIG_READ_FAILED**: 读取配置失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/dodge/config")
    config = response.json()
    print(f"闪避方式: {config['dodge_method']}, 敏感度: {config['sensitivity']}")
    ```
    """
    try:
        config_name = ctx.battle_assistant_config.dodge_assistant_config

        # 构建配置文件路径
        config_dir = os.path.join("config", "dodge")
        config_file = f"{config_name}.yml"
        config_path = os.path.join(config_dir, config_file)

        # 返回当前配置
        return DodgeAssistantConfig(
            dodge_method=config_name,
            use_gpu=ctx.model_config.flash_classifier_gpu,
            screenshot_interval=ctx.battle_assistant_config.screenshot_interval,
            gamepad_type=ctx.battle_assistant_config.gamepad_type
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIG_READ_FAILED",
                    "message": f"读取闪避助手配置失败: {str(e)}"
                }
            }
        )


@router.put("/dodge/config", summary="更新闪避助手配置")
def update_dodge_config(config: DodgeAssistantConfigUpdate, ctx: ZContext = Depends(get_ctx)):
    """
    更新闪避助手的配置

    ## 功能描述
    更新闪避助手的配置参数，支持部分更新。只需要提供需要修改的字段。

    ## 请求参数
    - **enabled** (可选): 是否启用闪避助手
    - **dodge_method** (可选): 闪避方式/配置名称
    - **sensitivity** (可选): 敏感度，范围0.0-1.0
    - **reaction_time** (可选): 反应时间，范围0.0-1.0秒

    ## 响应数据
    返回更新成功的消息

    ## 错误码
    - **CONFIG_UPDATE_FAILED**: 配置更新失败
    - **VALIDATION_ERROR**: 参数验证失败

    ## 使用示例
    ```python
    import requests
    data = {
        "dodge_method": "高级闪避",
        "sensitivity": 0.9
    }
    response = requests.put("http://localhost:8000/api/v1/battle-assistant/dodge/config", json=data)
    print(response.json()["message"])
    ```
    """
    try:
        updated_fields = []

        # 更新闪避方式
        if config.dodge_method is not None:
            ctx.battle_assistant_config.dodge_assistant_config = config.dodge_method
            updated_fields.append("dodge_method")

        # 更新GPU设置
        if config.use_gpu is not None:
            ctx.model_config.flash_classifier_gpu = config.use_gpu
            updated_fields.append("use_gpu")

        # 更新截图间隔
        if config.screenshot_interval is not None:
            ctx.battle_assistant_config.screenshot_interval = config.screenshot_interval
            updated_fields.append("screenshot_interval")

        # 更新手柄类型
        if config.gamepad_type is not None:
            ctx.battle_assistant_config.gamepad_type = _normalize_gamepad_type(config.gamepad_type)
            updated_fields.append("gamepad_type")

        # 保存配置
        if updated_fields:
            ctx.battle_assistant_config.save()
            if config.use_gpu is not None:
                ctx.model_config.save()

            # 广播配置更新事件
            broadcast_battle_assistant_event(
                BattleAssistantEventType.CONFIG_UPDATED,
                {
                    "config_type": "dodge",
                    "config_data": {field: getattr(config, field) for field in updated_fields if hasattr(config, field)}
                }
            )

        return {"message": "闪避助手配置更新成功"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIG_UPDATE_FAILED",
                    "message": f"更新闪避助手配置失败: {str(e)}"
                }
            }
        )


@router.get("/dodge/configs", response_model=ConfigListResponse, summary="获取闪避配置列表")
def get_dodge_configs(ctx: ZContext = Depends(get_ctx)):
    """
    获取所有可用的闪避配置文件列表
    """
    try:
        # 使用配置管理器获取配置列表
        config_list = config_manager.get_config_list("dodge")
        current_config = ctx.battle_assistant_config.dodge_assistant_config

        configs = []
        for config_info in config_list:
            configs.append(ConfigInfo(
                name=config_info["name"],
                description=config_info["description"],
                last_modified=config_info["last_modified"],
                file_size=config_info["file_size"]
            ))

        return ConfigListResponse(
            configs=configs,
            current_config=current_config
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIG_LIST_FAILED",
                    "message": f"获取闪避配置列表失败: {str(e)}"
                }
            }
        )


@router.delete("/dodge/configs/{name}", summary="删除闪避配置")
def delete_dodge_config(name: str, ctx: ZContext = Depends(get_ctx)):
    """
    删除指定的闪避配置文件
    """
    try:
        # 检查是否是当前使用的配置
        current_config = ctx.battle_assistant_config.dodge_assistant_config
        if current_config == name:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "CANNOT_DELETE_CURRENT",
                        "message": "不能删除当前正在使用的配置"
                    }
                }
            )

        # 使用配置管理器删除配置
        success, error_msg = config_manager.delete_config("dodge", name, allow_sample_delete=False)

        if not success:
            if "示例配置文件" in error_msg:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "CANNOT_DELETE_SAMPLE",
                            "message": error_msg
                        }
                    }
                )
            elif "不存在" in error_msg:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": {
                            "code": "CONFIG_NOT_FOUND",
                            "message": error_msg
                        }
                    }
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": {
                            "code": "CONFIG_DELETE_FAILED",
                            "message": error_msg
                        }
                    }
                )

        return {"message": f"配置文件 {name} 删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIG_DELETE_FAILED",
                    "message": f"删除配置文件失败: {str(e)}"
                }
            }
        )


# ============================================================================
# 闪避助手运行控制API端点
# ============================================================================

@router.post("/dodge/run", response_model=TaskResponse, summary="启动闪避助手")
async def start_dodge_assistant(ctx: ZContext = Depends(get_ctx)):
    """
    启动闪避助手任务

    ## 功能描述
    启动闪避助手自动化任务，开始监控游戏画面并自动执行闪避操作。

    **注意**: 此端点为兼容性端点，内部转发到统一控制接口。推荐使用 `/dodge/start` 端点。

    ## 返回数据
    - **task_id**: 任务唯一标识符，用于后续状态查询和控制
    - **message**: 启动状态消息

    ## 错误码
    - **TASK_ALREADY_RUNNING**: 已有任务正在运行
    - **TASK_START_FAILED**: 任务启动失败

    ## WebSocket事件
    启动后会通过WebSocket发送以下事件：
    - **task_started**: 任务开始事件
    - **battle_state_changed**: 战斗状态变化事件

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/dodge/run")
    task_info = response.json()
    print(f"任务ID: {task_info['task_id']}")
    ```
    """
    try:
        # 转发到统一控制接口
        result = await dodge_controller.start(ctx)

        # 转换响应格式以保持兼容性
        return TaskResponse(
            task_id=result.runId,
            message=result.message
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TASK_START_FAILED",
                    "message": f"启动闪避助手失败: {str(e)}"
                }
            }
        )


@router.post("/dodge/stop", summary="停止闪避助手")
async def stop_dodge_assistant(ctx: ZContext = Depends(get_ctx)):
    """
    停止闪避助手任务

    ## 功能描述
    停止当前运行的闪避助手任务，取消所有相关的异步任务。

    **注意**: 此端点为兼容性端点，内部转发到统一控制接口。推荐使用 `/dodge/stop` 统一接口端点。

    ## 返回数据
    返回停止操作的结果消息，包括取消的任务数量

    ## 错误码
    - **TASK_STOP_FAILED**: 任务停止失败

    ## WebSocket事件
    停止后会通过WebSocket发送以下事件：
    - **task_completed**: 任务完成事件
    - **task_cancelled**: 任务取消事件

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/dodge/stop")
    print(response.json()["message"])
    ```
    """
    try:
        # 转发到统一控制接口
        result = await dodge_controller.stop()

        # 转换响应格式以保持兼容性
        return {
            "message": result.message
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TASK_STOP_FAILED",
                    "message": f"停止闪避助手失败: {str(e)}"
                }
            }
        )


@router.get("/battle-state", response_model=BattleState, summary="获取实时战斗状态")
def get_battle_state(ctx: ZContext = Depends(get_ctx)):
    """
    获取当前的战斗状态，包括敌人检测、当前动作和系统状态

    ## 功能描述
    实时获取当前战斗状态信息，支持战斗状态监控、UI展示和性能分析。

    ## 返回数据
    - **is_in_battle**: 是否在战斗中
    - **current_action**: 当前执行的动作
    - **enemies_detected**: 检测到的敌人数量
    - **last_update**: 最后更新时间
    - **performance_metrics**: 性能指标数据
      - **last_check_distance**: 最后检查距离
      - **check_intervals**: 各种检查间隔时间
      - **context_running**: 上下文是否运行中
      - **running_tasks**: 运行中的任务数量

    ## 错误处理
    如果获取状态失败，会返回默认状态并在performance_metrics中包含错误信息

    ## WebSocket支持
    状态变化时会自动通过WebSocket广播battle_state_changed事件

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/battle-state")
    state = response.json()
    print(f"战斗状态: {'战斗中' if state['is_in_battle'] else '非战斗'}")
    print(f"当前动作: {state['current_action']}")
    ```
    """
    try:
        # 获取基础战斗状态信息
        is_in_battle = False
        current_action = None
        enemies_detected = 0
        performance_metrics = {}

        # 如果有自动战斗操作器在运行，获取详细状态
        if ctx.auto_op is not None:
            auto_battle_context = ctx.auto_op.auto_battle_context

            # 获取战斗状态
            is_in_battle = auto_battle_context.last_check_in_battle

            # 获取当前动作（从状态记录器中获取最近的动作）
            if hasattr(ctx.auto_op, 'state_recorders') and ctx.auto_op.state_recorders:
                # 获取最近的状态记录
                latest_action_state = None
                latest_action_time = 0
                latest_any_state = None
                latest_any_time = 0

                for recorder in ctx.auto_op.state_recorders.values():
                    if recorder.last_record_time > 0:  # 检查是否有有效的记录时间
                        if recorder.last_record_time > latest_any_time:
                            latest_any_time = recorder.last_record_time
                            latest_any_state = recorder.state_name

                # 使用最新状态，与PySide GUI保持一致
                if latest_any_state:
                    current_action = latest_any_state

            # 获取敌人检测信息
            if hasattr(auto_battle_context, 'target_context'):
                # 从目标上下文获取敌人数量（这里需要根据实际实现调整）
                enemies_detected = 0  # 默认值，实际需要从目标检测系统获取

            # 收集性能指标
            performance_metrics = {
                "last_check_distance": auto_battle_context.last_check_distance,
                "without_distance_times": auto_battle_context.without_distance_times,
                "with_distance_times": auto_battle_context.with_distance_times,
                "check_intervals": {
                    "chain": auto_battle_context._check_chain_interval,
                    "quick": auto_battle_context._check_quick_interval,
                    "end": auto_battle_context._check_end_interval,
                    "distance": auto_battle_context._check_distance_interval
                }
            }

            # 添加代理状态信息
            if hasattr(auto_battle_context, 'agent_context'):
                agent_context = auto_battle_context.agent_context
                performance_metrics["agent_info"] = {
                    "current_agent": getattr(agent_context, 'current_agent_name', None),
                    "agent_status": getattr(agent_context, 'current_agent_status', None)
                }

        # 如果上下文正在运行，表示可能在战斗中
        if ctx.run_context.is_context_running:
            # 可以根据运行的应用类型推断状态
            performance_metrics["context_running"] = True
            performance_metrics["running_tasks"] = len(_registry.list_statuses())

            # 如果没有auto_op但上下文在运行，可能是其他类型的任务
            if ctx.auto_op is None:
                current_action = "任务运行中"
        else:
            performance_metrics["context_running"] = False
            performance_metrics["running_tasks"] = 0

            # 如果没有任何任务运行，显示待机状态
            if current_action is None:
                current_action = "待机"

        battle_state = BattleState(
            is_in_battle=is_in_battle,
            current_action=current_action,
            enemies_detected=enemies_detected,
            last_update=datetime.now(),
            performance_metrics=performance_metrics
        )

        # 如果有战斗助手桥接，广播战斗状态更新
        if hasattr(ctx, '_battle_assistant_bridge'):
            bridge = getattr(ctx, '_battle_assistant_bridge')
            bridge.broadcast_battle_state({
                "is_in_battle": is_in_battle,
                "current_action": current_action,
                "enemies_detected": enemies_detected,
                "last_update": datetime.now().isoformat(),
                "performance_metrics": performance_metrics
            })

        return battle_state

    except Exception as e:
        # 如果获取状态失败，返回默认状态但记录错误
        log.error(f"获取战斗状态失败: {str(e)}", exc_info=True)

        # 广播错误事件
        broadcast_battle_assistant_event(
            BattleAssistantEventType.ERROR_OCCURRED,
            {
                "message": f"获取战斗状态失败: {str(e)}",
                "details": {"error_type": "battle_state_error"}
            }
        )

        return BattleState(
            is_in_battle=False,
            current_action=None,
            enemies_detected=0,
            last_update=datetime.now(),
            performance_metrics={"error": str(e)}
        )

# ============================================================================
# 自动战斗运行控制API端点
# ============================================================================

@router.post("/auto-battle/run", response_model=TaskResponse, summary="启动自动战斗")
async def start_auto_battle(ctx: ZContext = Depends(get_ctx)):
    """
    启动自动战斗任务（正常模式）

    ## 功能描述
    启动自动战斗任务，使用当前配置的战斗策略自动执行战斗操作。

    **注意**: 此端点为兼容性端点，内部转发到统一控制接口。推荐使用 `/auto-battle/start` 端点。

    ## 返回数据
    - **task_id**: 任务唯一标识符
    - **message**: 启动状态消息

    ## 错误码
    - **TASK_ALREADY_RUNNING**: 已有任务正在运行
    - **TASK_START_FAILED**: 任务启动失败

    ## WebSocket事件
    - **task_started**: 任务开始
    - **task_progress**: 任务进度更新
    - **battle_state_changed**: 战斗状态变化

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/auto-battle/run")
    task_info = response.json()
    print(f"自动战斗任务ID: {task_info['task_id']}")
    ```
    """
    try:
        # 转发到统一控制接口
        result = await auto_battle_controller.start(ctx)

        # 转换响应格式以保持兼容性
        return TaskResponse(
            task_id=result.runId,
            message=result.message
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TASK_START_FAILED",
                    "message": f"启动自动战斗失败: {str(e)}"
                }
            }
        )


@router.post("/auto-battle/debug", response_model=TaskResponse, summary="启动自动战斗调试")
async def start_auto_battle_debug(ctx: ZContext = Depends(get_ctx)):
    """
    启动自动战斗任务（调试模式）

    ## 功能描述
    启动自动战斗调试模式，执行一个战斗周期并提供详细的调试信息和性能分析。

    ## 返回数据
    - **task_id**: 任务唯一标识符
    - **message**: 启动状态消息

    ## 调试特性
    - 执行单次战斗周期
    - 提供详细的状态日志
    - 包含性能指标分析
    - 支持步骤级别的调试信息

    ## 错误码
    - **TASK_ALREADY_RUNNING**: 已有任务正在运行
    - **TASK_START_FAILED**: 任务启动失败

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/auto-battle/debug")
    task_info = response.json()
    print(f"调试任务ID: {task_info['task_id']}")
    ```
    """
    try:
        # 检查是否已有任务在运行
        if ctx.run_context.is_context_running:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "TASK_ALREADY_RUNNING",
                        "message": "已有任务正在运行，请先停止当前任务"
                    }
                }
            )

        def _factory() -> asyncio.Task:
            async def runner():
                loop = asyncio.get_running_loop()

                def _exec():
                    from zzz_od.application.battle_assistant.operation_debug.operation_debug_app import OperationDebugApp
                    app = OperationDebugApp(ctx)
                    app.execute()

                return await loop.run_in_executor(None, _exec)

            return asyncio.create_task(runner())

        # 创建任务
        run_id = _registry.create(_factory)

        # 附加事件桥接用于WebSocket通信
        attach_run_event_bridge(ctx, run_id)
        attach_battle_assistant_event_bridge(ctx, run_id)

        return TaskResponse(
            task_id=run_id,
            message="自动战斗调试已启动"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TASK_START_FAILED",
                    "message": f"启动自动战斗调试失败: {str(e)}"
                }
            }
        )


@router.post("/auto-battle/stop", summary="停止自动战斗")
def stop_auto_battle(ctx: ZContext = Depends(get_ctx)):
    """
    停止自动战斗任务

    ## 功能描述
    停止当前运行的自动战斗任务，取消所有相关的异步任务。

    ## 返回数据
    返回停止操作的结果消息，包括取消的任务数量

    ## 错误码
    - **TASK_STOP_FAILED**: 任务停止失败

    ## WebSocket事件
    - **task_completed**: 任务完成事件
    - **task_cancelled**: 任务取消事件

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/auto-battle/stop")
    print(response.json()["message"])
    ```
    """
    try:
        # 停止上下文运行
        ctx.run_context.stop_running()

        # 取消所有相关任务
        statuses = _registry.list_statuses()
        cancelled_count = 0

        for status in statuses:
            if status.status.value in ["pending", "running"]:
                if _registry.cancel(status.runId):
                    cancelled_count += 1

        return {
            "message": f"自动战斗已停止，取消了 {cancelled_count} 个任务"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TASK_STOP_FAILED",
                    "message": f"停止自动战斗失败: {str(e)}"
                }
            }
        )


# ============================================================================
# 指令调试模板管理API端点
# ============================================================================

@router.get("/operation-debug/templates", response_model=TemplateListResponse, summary="获取操作模板列表")
def get_operation_debug_templates(ctx: ZContext = Depends(get_ctx)):
    """
    获取所有可用的操作模板列表，包括子目录模板

    ## 功能描述
    返回系统中所有可用的操作模板列表，包括子目录中的模板文件。

    ## 返回数据
    - **templates**: 模板列表
      - **name**: 模板名称
      - **path**: 模板文件路径
      - **description**: 模板描述
      - **last_modified**: 最后修改时间
      - **file_size**: 文件大小（字节）

    ## 错误码
    - **TEMPLATE_LIST_FAILED**: 获取模板列表失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/operation-debug/templates")
    templates = response.json()["templates"]
    print(f"可用模板: {[t['name'] for t in templates]}")
    ```
    """
    try:
        # 使用模板管理器获取模板列表
        template_list = template_manager.get_template_list()

        templates = []
        for template_info in template_list:
            templates.append(TemplateInfo(
                name=template_info["name"],
                path=template_info["path"],
                description=template_info["description"],
                last_modified=template_info["last_modified"],
                file_size=template_info["file_size"]
            ))

        return TemplateListResponse(templates=templates)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TEMPLATE_LIST_FAILED",
                    "message": f"获取操作模板列表失败: {str(e)}"
                }
            }
        )


@router.get("/operation-debug/config", response_model=OperationDebugConfig, summary="获取指令调试配置")
def get_operation_debug_config(ctx: ZContext = Depends(get_ctx)):
    """
    获取当前指令调试的配置

    ## 功能描述
    返回当前指令调试的详细配置信息，包括选定的模板、重复模式和手柄设置。

    ## 返回数据
    - **template_name**: 当前选择的操作模板名称
    - **repeat_mode**: 是否启用重复模式
    - **gamepad_type**: 手柄类型设置

    ## 错误码
    - **CONFIG_READ_FAILED**: 读取配置失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/operation-debug/config")
    config = response.json()
    print(f"当前模板: {config['template_name']}")
    print(f"重复模式: {'开启' if config['repeat_mode'] else '关闭'}")
    ```
    """
    try:
        # 从配置中获取当前模板名称和设置
        # 如果配置不存在，返回默认配置
        template_name = getattr(ctx.battle_assistant_config, 'debug_operation_config', "安比-3A特殊攻击")
        repeat_mode = getattr(ctx.battle_assistant_config, 'debug_operation_repeat', True)
        gamepad_type = getattr(ctx.battle_assistant_config, 'gamepad_type', "none")

        return OperationDebugConfig(
            template_name=template_name,
            repeat_mode=repeat_mode,
            gamepad_type=gamepad_type
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIG_READ_FAILED",
                    "message": f"读取指令调试配置失败: {str(e)}"
                }
            }
        )


@router.put("/operation-debug/config", summary="更新指令调试配置")
def update_operation_debug_config(config: OperationDebugConfigUpdate, ctx: ZContext = Depends(get_ctx)):
    """
    更新指令调试的配置

    ## 功能描述
    更新指令调试的配置参数，支持部分更新。只需要提供需要修改的字段。

    ## 请求参数
    - **template_name** (可选): 操作模板名称
    - **repeat_mode** (可选): 重复模式，布尔值
    - **gamepad_type** (可选): 手柄类型

    ## 响应数据
    返回更新成功的消息

    ## 错误码
    - **TEMPLATE_NOT_FOUND**: 指定的模板不存在
    - **CONFIG_UPDATE_FAILED**: 配置更新失败
    - **VALIDATION_ERROR**: 参数验证失败

    ## 使用示例
    ```python
    import requests
    data = {
        "template_name": "安比-3A特殊攻击",
        "repeat_mode": True
    }
    response = requests.put("http://localhost:8000/api/v1/battle-assistant/operation-debug/config", json=data)
    print(response.json()["message"])
    ```
    """
    try:
        # 更新模板名称（如果提供）
        if config.template_name is not None:
            # 验证模板是否存在
            if not template_manager.template_exists(config.template_name):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "TEMPLATE_NOT_FOUND",
                            "message": f"模板 {config.template_name} 不存在"
                        }
                    }
                )

            ctx.battle_assistant_config.debug_operation_config = config.template_name

        # 更新重复模式（如果提供）
        if config.repeat_mode is not None:
            ctx.battle_assistant_config.debug_operation_repeat = config.repeat_mode

        # 更新手柄类型（如果提供）
        if config.gamepad_type is not None:
            ctx.battle_assistant_config.gamepad_type = _normalize_gamepad_type(config.gamepad_type)

        # 保存配置
        ctx.battle_assistant_config.save()

        # 广播配置更新事件
        broadcast_battle_assistant_event(
            BattleAssistantEventType.CONFIG_UPDATED,
            {
                "config_type": "operation_debug",
                "config_data": {
                    "template_name": config.template_name,
                    "repeat_mode": config.repeat_mode,
                    "gamepad_type": config.gamepad_type
                }
            }
        )

        return {"message": "指令调试配置更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CONFIG_UPDATE_FAILED",
                    "message": f"更新指令调试配置失败: {str(e)}"
                }
            }
        )


@router.delete("/operation-debug/templates/{name}", summary="删除操作模板")
def delete_operation_debug_template(name: str, ctx: ZContext = Depends(get_ctx)):
    """
    删除指定的操作模板文件
    """
    try:
        # 检查是否是当前使用的模板
        current_template = getattr(ctx.battle_assistant_config, 'debug_operation_config', None)
        if current_template == name:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "CANNOT_DELETE_CURRENT",
                        "message": "不能删除当前正在使用的模板"
                    }
                }
            )

        # 使用模板管理器删除模板
        success, error_msg = template_manager.delete_template(name, allow_sample_delete=False)

        if not success:
            if "示例模板文件" in error_msg:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "CANNOT_DELETE_SAMPLE",
                            "message": error_msg
                        }
                    }
                )
            elif "不存在" in error_msg:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": {
                            "code": "TEMPLATE_NOT_FOUND",
                            "message": error_msg
                        }
                    }
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": {
                            "code": "TEMPLATE_DELETE_FAILED",
                            "message": error_msg
                        }
                    }
                )

        return {"message": f"模板文件 {name} 删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TEMPLATE_DELETE_FAILED",
                    "message": f"删除模板文件失败: {str(e)}"
                }
            }
        )


# ============================================================================
# 指令调试运行控制API端点
# ============================================================================

@router.post("/operation-debug/run", response_model=TaskResponse, summary="启动指令调试")
async def start_operation_debug(ctx: ZContext = Depends(get_ctx)):
    """
    启动指令调试任务
    支持重复模式和单次执行模式
    """
    try:
        # 检查是否已有任务在运行
        if ctx.run_context.is_context_running:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "TASK_ALREADY_RUNNING",
                        "message": "已有任务正在运行，请先停止当前任务"
                    }
                }
            )

        # 验证模板是否存在
        template_name = getattr(ctx.battle_assistant_config, 'debug_operation_config', "安比-3A特殊攻击")

        if not template_manager.template_exists(template_name):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "TEMPLATE_NOT_FOUND",
                        "message": f"模板 {template_name} 不存在，请先选择有效的模板"
                    }
                }
            )

        def _factory() -> asyncio.Task:
            async def runner():
                loop = asyncio.get_running_loop()

                def _exec():
                    from zzz_od.application.battle_assistant.operation_debug.operation_debug_app import OperationDebugApp
                    app = OperationDebugApp(ctx)
                    app.execute()

                return await loop.run_in_executor(None, _exec)

            return asyncio.create_task(runner())

        # 创建任务
        run_id = _registry.create(_factory)

        # 附加事件桥接用于WebSocket通信
        attach_run_event_bridge(ctx, run_id)
        attach_battle_assistant_event_bridge(ctx, run_id)

        # 获取重复模式状态用于响应消息
        repeat_mode = getattr(ctx.battle_assistant_config, 'debug_operation_repeat', True)
        mode_text = "重复模式" if repeat_mode else "单次执行模式"

        return TaskResponse(
            task_id=run_id,
            message=f"指令调试已启动 ({mode_text})"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TASK_START_FAILED",
                    "message": f"启动指令调试失败: {str(e)}"
                }
            }
        )


@router.post("/operation-debug/start", response_model=ControlResponse, summary="启动指令调试（统一接口）")
async def start_operation_debug_unified():
    """
    启动指令调试任务（统一控制接口）

    ## 功能描述
    使用统一控制接口启动指令调试任务，按照当前配置的模板执行调试操作。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 任务运行ID（成功时）
    - **capabilities**: 模块能力标识

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败 (500)
    - **TASK_ALREADY_RUNNING**: 任务已在运行 (409)
    - **TEMPLATE_NOT_FOUND**: 模板不存在 (404)

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/operation-debug/start")
    result = response.json()
    print(f"启动结果: {result['message']}")
    ```
    """
    return await operation_debug_controller.start()


@router.post("/operation-debug/stop", response_model=ControlResponse, summary="停止指令调试（统一接口）")
async def stop_operation_debug_unified():
    """
    停止指令调试任务（统一控制接口）

    ## 功能描述
    使用统一控制接口停止当前运行的指令调试任务。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/operation-debug/stop")
    result = response.json()
    print(f"停止结果: {result['message']}")
    ```
    """
    return await operation_debug_controller.stop()


@router.get("/operation-debug/status", response_model=StatusResponse, summary="获取指令调试状态（统一接口）")
async def get_operation_debug_status_unified():
    """
    获取指令调试的运行状态（统一控制接口）

    ## 功能描述
    返回指令调试的当前运行状态，使用统一的状态响应格式。

    ## 返回数据
    - **is_running**: 是否正在运行
    - **context_state**: 上下文状态 (idle | running | paused)
    - **running_tasks**: 运行中的任务数量
    - **message**: 状态消息
    - **runId**: 当前运行ID
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/operation-debug/status")
    status = response.json()
    print(f"运行状态: {status['context_state']}")
    ```
    """
    return await operation_debug_controller.status()


@router.post("/operation-debug/pause", response_model=ControlResponse, summary="暂停指令调试（统一接口）")
async def pause_operation_debug_unified():
    """
    暂停指令调试任务

    ## 功能描述
    暂停当前正在运行的指令调试任务，保持状态以便后续恢复。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/operation-debug/pause")
    result = response.json()
    print(f"暂停结果: {result['ok']}, 消息: {result['message']}")
    ```
    """
    return await operation_debug_controller.pause()


@router.post("/operation-debug/resume", response_model=ControlResponse, summary="恢复指令调试（统一接口）")
async def resume_operation_debug_unified():
    """
    恢复指令调试任务

    ## 功能描述
    恢复之前暂停的指令调试任务执行。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/operation-debug/resume")
    result = response.json()
    print(f"恢复结果: {result['ok']}, 消息: {result['message']}")
    ```
    """
    return await operation_debug_controller.resume()


@router.get("/operation-debug/logs", response_model=LogReplayResponse, summary="获取指令调试运行日志")
async def operation_debug_logs(
    runId: str = None,
    tail: int = 1000
) -> LogReplayResponse:
    """
    获取指令调试运行日志回放

    ## 功能描述
    获取指定runId的指令调试运行日志，支持回放最近的日志记录。所有时间戳使用UTC ISO8601格式。

    ## 查询参数
    - **runId** (可选): 运行ID，不提供则使用当前运行的ID
    - **tail** (可选): 返回最后N条日志，默认1000，最大2000

    ## 返回数据
    - **logs**: 日志条目列表
      - **timestamp**: 时间戳，UTC ISO8601格式（2025-09-20T12:34:56.789Z）
      - **level**: 日志级别 (debug | info | warning | error)
      - **message**: 日志消息
      - **runId**: 运行ID
      - **module**: 模块名称
      - **seq**: 序列号
      - **extra**: 额外信息
    - **total_count**: 返回的日志条数
    - **runId**: 查询的运行ID
    - **module**: 模块名称
    - **has_more**: 是否还有更多日志（当前实现中始终为false）
    - **message**: 响应消息

    ## 默认策略
    - 当runId不存在时，返回空日志列表和说明消息
    - 当无日志记录时，返回"暂无日志记录"消息
    - 日志条数限制在2000条以内

    ## 使用示例
    ```python
    import requests

    # 获取当前运行的最新1000条日志
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/operation-debug/logs")

    # 获取指定runId的最新500条日志
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/operation-debug/logs?runId=abc123&tail=500")

    logs = response.json()
    for log in logs['logs']:
        print(f"[{log['timestamp']}] {log['level'].upper()}: {log['message']}")
    ```
    """
    return await operation_debug_controller.get_logs(runId, tail)


@router.post("/operation-debug/stop", summary="停止指令调试")
def stop_operation_debug(ctx: ZContext = Depends(get_ctx)):
    """
    停止指令调试任务
    """
    try:
        # 停止上下文运行
        ctx.run_context.stop_running()

        # 取消所有相关任务
        statuses = _registry.list_statuses()
        cancelled_count = 0

        for status in statuses:
            if status.status.value in ["pending", "running"]:
                if _registry.cancel(status.runId):
                    cancelled_count += 1

        return {
            "message": f"指令调试已停止，取消了 {cancelled_count} 个任务"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TASK_STOP_FAILED",
                    "message": f"停止指令调试失败: {str(e)}"
                }
            }
        )


# ============================================================================
# 配置信息管理API端点
# ============================================================================

@router.get("/settings", response_model=BattleAssistantSettings, summary="获取战斗助手设置")
def get_battle_assistant_settings(ctx: ZContext = Depends(get_ctx)):
    """
    获取当前战斗助手的系统设置，包括GPU使用、截图间隔和手柄类型

    ## 功能描述
    返回战斗助手的全局系统设置，这些设置影响所有战斗助手功能的性能和行为。

    ## 返回数据
    - **use_gpu**: 是否使用GPU加速
    - **screenshot_interval**: 截图间隔时间（秒）
    - **gamepad_type**: 当前配置的手柄类型

    ## 错误码
    - **SETTINGS_READ_FAILED**: 读取设置失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/settings")
    settings = response.json()
    print(f"GPU: {'启用' if settings['use_gpu'] else '禁用'}")
    print(f"截图间隔: {settings['screenshot_interval']}秒")
    ```
    """
    try:
        return BattleAssistantSettings(
            use_gpu=getattr(ctx.battle_assistant_config, 'use_gpu', True),
            screenshot_interval=getattr(ctx.battle_assistant_config, 'screenshot_interval', 0.02),
            gamepad_type=getattr(ctx.battle_assistant_config, 'gamepad_type', "none")
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "SETTINGS_READ_FAILED",
                    "message": f"读取战斗助手设置失败: {str(e)}"
                }
            }
        )


@router.put("/settings", summary="更新战斗助手设置")
def update_battle_assistant_settings(settings: BattleAssistantSettingsUpdate, ctx: ZContext = Depends(get_ctx)):
    """
    更新战斗助手的系统设置

    ## 功能描述
    更新战斗助手的全局系统设置，支持部分更新。只需要提供需要修改的字段。

    ## 请求参数
    - **use_gpu** (可选): 是否使用GPU，布尔值
    - **screenshot_interval** (可选): 截图间隔，范围0.01-1.0秒
    - **gamepad_type** (可选): 手柄类型，支持的类型见/settings/gamepad-types

    ## 响应数据
    返回更新成功的消息

    ## 错误码
    - **INVALID_SCREENSHOT_INTERVAL**: 截图间隔超出有效范围
    - **UNSUPPORTED_GAMEPAD_TYPE**: 不支持的手柄类型
    - **SETTINGS_UPDATE_FAILED**: 设置更新失败

    ## 使用示例
    ```python
    import requests
    data = {
        "use_gpu": True,
        "screenshot_interval": 0.03,
        "gamepad_type": "xbox"
    }
    response = requests.put("http://localhost:8000/api/v1/battle-assistant/settings", json=data)
    print(response.json()["message"])
    ```
    """
    try:
        # 更新GPU使用设置（如果提供）
        if settings.use_gpu is not None:
            ctx.battle_assistant_config.use_gpu = settings.use_gpu

        # 更新截图间隔（如果提供）
        if settings.screenshot_interval is not None:
            # 验证截图间隔在可接受范围内
            if settings.screenshot_interval < 0.01 or settings.screenshot_interval > 1.0:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "INVALID_SCREENSHOT_INTERVAL",
                            "message": "截图间隔必须在0.01到1.0秒之间"
                        }
                    }
                )
            ctx.battle_assistant_config.screenshot_interval = settings.screenshot_interval

        # 更新手柄类型（如果提供）
        if settings.gamepad_type is not None:
            # 验证手柄类型是否受支持
            supported_gamepad_types = ["none", "xbox", "ds4"]
            if settings.gamepad_type not in supported_gamepad_types:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "UNSUPPORTED_GAMEPAD_TYPE",
                            "message": f"不支持的手柄类型: {settings.gamepad_type}"
                        }
                    }
                )
            ctx.battle_assistant_config.gamepad_type = settings.gamepad_type

        # 保存配置
        ctx.battle_assistant_config.save()

        return {"message": "战斗助手设置更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "SETTINGS_UPDATE_FAILED",
                    "message": f"更新战斗助手设置失败: {str(e)}"
                }
            }
        )


@router.get("/settings/gamepad-types", response_model=GamepadTypesResponse, summary="获取支持的手柄类型列表")
def get_gamepad_types():
    """
    获取所有支持的手柄类型列表及其描述

    ## 功能描述
    返回系统支持的所有手柄类型，包括显示名称、描述和支持状态。

    ## 返回数据
    - **gamepad_types**: 手柄类型列表
      - **value**: 手柄类型值（用于配置）
      - **display_name**: 显示名称
      - **description**: 详细描述
      - **supported**: 是否支持

    ## 支持的手柄类型
    - **none**: 无手柄（仅键盘）
    - **xbox**: Xbox系列手柄
    - **ds4**: PlayStation 4 DualShock 4手柄

    ## 错误码
    - **GAMEPAD_TYPES_FAILED**: 获取手柄类型列表失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/settings/gamepad-types")
    types = response.json()["gamepad_types"]
    for gamepad_type in types:
        print(f"{gamepad_type['display_name']}: {gamepad_type['description']}")
    ```
    """
    try:
        gamepad_types = [
            GamepadTypeInfo(
                value="none",
                display_name="无手柄",
                description="不使用手柄，仅使用键盘操作",
                supported=True
            ),
            GamepadTypeInfo(
                value="xbox",
                display_name="Xbox手柄",
                description="Microsoft Xbox系列手柄",
                supported=True
            ),
            GamepadTypeInfo(
                value="ds4",
                display_name="DS4手柄",
                description="Sony PlayStation 4 DualShock 4手柄",
                supported=True
            )
        ]

        return GamepadTypesResponse(gamepad_types=gamepad_types)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "GAMEPAD_TYPES_FAILED",
                    "message": f"获取手柄类型列表失败: {str(e)}"
                }
            }
        )


@router.put("/settings/gpu", summary="更新GPU设置")
def update_gpu_setting(use_gpu: bool, ctx: ZContext = Depends(get_ctx)):
    """
    更新GPU使用设置的专用端点

    ## 功能描述
    专门用于更新GPU使用设置的端点，提供快速的GPU开关功能。

    ## 请求参数
    - **use_gpu**: 是否使用GPU，布尔值

    ## 响应数据
    - **message**: 更新结果消息
    - **use_gpu**: 更新后的GPU设置状态

    ## 错误码
    - **GPU_SETTING_UPDATE_FAILED**: GPU设置更新失败

    ## WebSocket事件
    - **config_updated**: 配置更新事件

    ## 使用示例
    ```python
    import requests
    response = requests.put("http://localhost:8000/api/v1/battle-assistant/settings/gpu", params={"use_gpu": True})
    result = response.json()
    print(result["message"])
    ```
    """
    try:
        ctx.battle_assistant_config.use_gpu = use_gpu
        ctx.battle_assistant_config.save()

        # 广播配置更新事件
        broadcast_battle_assistant_event(
            BattleAssistantEventType.CONFIG_UPDATED,
            {
                "config_type": "gpu_setting",
                "config_data": {"use_gpu": use_gpu}
            }
        )

        return {
            "message": f"GPU设置已更新为: {'启用' if use_gpu else '禁用'}",
            "use_gpu": use_gpu
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "GPU_SETTING_UPDATE_FAILED",
                    "message": f"更新GPU设置失败: {str(e)}"
                }
            }
        )


@router.put("/settings/screenshot-interval", summary="更新截图间隔设置")
def update_screenshot_interval_setting(screenshot_interval: float, ctx: ZContext = Depends(get_ctx)):
    """
    更新截图间隔设置的专用端点
    """
    try:
        # 验证截图间隔在可接受范围内
        if screenshot_interval < 0.01 or screenshot_interval > 1.0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_SCREENSHOT_INTERVAL",
                        "message": "截图间隔必须在0.01到1.0秒之间"
                    }
                }
            )

        ctx.battle_assistant_config.screenshot_interval = screenshot_interval
        ctx.battle_assistant_config.save()

        # 广播配置更新事件
        broadcast_battle_assistant_event(
            BattleAssistantEventType.CONFIG_UPDATED,
            {
                "config_type": "screenshot_interval",
                "config_data": {"screenshot_interval": screenshot_interval}
            }
        )

        return {
            "message": f"截图间隔已更新为: {screenshot_interval}秒",
            "screenshot_interval": screenshot_interval
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "SCREENSHOT_INTERVAL_UPDATE_FAILED",
                    "message": f"更新截图间隔设置失败: {str(e)}"
                }
            }
        )


@router.put("/settings/gamepad", summary="更新手柄类型设置")
def update_gamepad_setting(gamepad_type: str, ctx: ZContext = Depends(get_ctx)):
    """
    更新手柄类型设置的专用端点
    """
    try:
        # 验证手柄类型是否受支持
        supported_gamepad_types = ["none", "xbox", "ps4", "ps5", "switch_pro"]
        if gamepad_type not in supported_gamepad_types:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "UNSUPPORTED_GAMEPAD_TYPE",
                        "message": f"不支持的手柄类型: {gamepad_type}，支持的类型: {', '.join(supported_gamepad_types)}"
                    }
                }
            )

        ctx.battle_assistant_config.gamepad_type = gamepad_type
        ctx.battle_assistant_config.save()

        # 广播配置更新事件
        broadcast_battle_assistant_event(
            BattleAssistantEventType.CONFIG_UPDATED,
            {
                "config_type": "gamepad_type",
                "config_data": {"gamepad_type": gamepad_type}
            }
        )

        return {
            "message": f"手柄类型已更新为: {gamepad_type}",
            "gamepad_type": gamepad_type
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "GAMEPAD_SETTING_UPDATE_FAILED",
                    "message": f"更新手柄类型设置失败: {str(e)}"
                }
            }
        )

# ============================================================================
# 战斗状态监控辅助功能
# ============================================================================

def _collect_battle_performance_metrics(ctx: ZContext) -> dict:
    """
    收集战斗性能指标
    """
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "context_running": ctx.run_context.is_context_running,
        "running_tasks": len(_registry.list_statuses()),
        "system_info": {}
    }

    # 收集任务状态信息
    task_statuses = _registry.list_statuses()
    metrics["task_details"] = []

    for status in task_statuses:
        task_detail = {
            "run_id": getattr(status, 'runId', None),
            "status": getattr(status.status, 'value', str(status.status)) if hasattr(status, 'status') else 'unknown'
        }

        # 安全地获取时间属性
        def safe_time_format(time_attr):
            if time_attr is None:
                return None
            if isinstance(time_attr, str):
                return time_attr  # 已经是字符串，直接返回
            if hasattr(time_attr, 'isoformat'):
                return time_attr.isoformat()  # datetime对象
            return str(time_attr)  # 其他类型转为字符串

        if hasattr(status, 'createdAt') and status.createdAt:
            task_detail["created_at"] = safe_time_format(status.createdAt)
        elif hasattr(status, 'created_at') and status.created_at:
            task_detail["created_at"] = safe_time_format(status.created_at)
        else:
            task_detail["created_at"] = None

        if hasattr(status, 'startedAt') and status.startedAt:
            task_detail["started_at"] = safe_time_format(status.startedAt)
        elif hasattr(status, 'started_at') and status.started_at:
            task_detail["started_at"] = safe_time_format(status.started_at)
        else:
            task_detail["started_at"] = None

        if hasattr(status, 'finishedAt') and status.finishedAt:
            task_detail["finished_at"] = safe_time_format(status.finishedAt)
        elif hasattr(status, 'finished_at') and status.finished_at:
            task_detail["finished_at"] = safe_time_format(status.finished_at)
        else:
            task_detail["finished_at"] = None

        metrics["task_details"].append(task_detail)

    # 收集配置信息
    if hasattr(ctx, 'battle_assistant_config'):
        metrics["config_info"] = {
            "use_gpu": ctx.battle_assistant_config.use_gpu,
            "screenshot_interval": ctx.battle_assistant_config.screenshot_interval,
            "gamepad_type": ctx.battle_assistant_config.gamepad_type,
            "auto_battle_config": getattr(ctx.battle_assistant_config, 'auto_battle_config', None),
            "dodge_assistant_config": getattr(ctx.battle_assistant_config, 'dodge_assistant_config', None)
        }

    return metrics


def _collect_battle_state_info(ctx: ZContext) -> dict:
    """
    收集详细的战斗状态信息
    """
    battle_info = {
        "is_in_battle": False,
        "current_action": None,
        "enemies_detected": 0,
        "battle_context_available": False,
        "agent_info": {},
        "dodge_info": {},
        "target_info": {}
    }

    # 如果有自动战斗操作器在运行
    if ctx.auto_op is not None:
        battle_info["battle_context_available"] = True
        auto_battle_context = ctx.auto_op.auto_battle_context

        # 基础战斗状态
        battle_info["is_in_battle"] = auto_battle_context.last_check_in_battle

        # 获取最近的动作状态
        if hasattr(ctx.auto_op, 'state_recorders') and ctx.auto_op.state_recorders:
            latest_action_state = None
            latest_action_time = 0
            latest_any_state = None
            latest_any_time = 0

            for recorder_name, recorder in ctx.auto_op.state_recorders.items():
                if recorder.last_record_time > 0:  # 检查是否有有效的记录时间
                    # 记录所有状态中最新的
                    if recorder.last_record_time > latest_any_time:
                        latest_any_time = recorder.last_record_time
                        latest_any_state = recorder.state_name

            # 使用最新状态，与PySide GUI保持一致
            if latest_any_state:
                battle_info["current_action"] = latest_any_state
                battle_info["last_action_time"] = latest_any_time

        # 代理信息
        if hasattr(auto_battle_context, 'agent_context'):
            agent_context = auto_battle_context.agent_context
            battle_info["agent_info"] = {
                "current_agent": getattr(agent_context, 'current_agent_name', None),
                "agent_status": getattr(agent_context, 'current_agent_status', None),
                "last_check_time": getattr(agent_context, '_last_check_agent_time', 0)
            }

        # 闪避信息
        if hasattr(auto_battle_context, 'dodge_context'):
            dodge_context = auto_battle_context.dodge_context
            battle_info["dodge_info"] = {
                "last_check_time": getattr(dodge_context, '_last_check_dodge_time', 0),
                "dodge_enabled": getattr(dodge_context, 'dodge_enabled', False)
            }

        # 目标信息
        if hasattr(auto_battle_context, 'target_context'):
            target_context = auto_battle_context.target_context
            battle_info["target_info"] = {
                "last_check_time": getattr(target_context, '_last_check_target_time', 0),
                "target_locked": getattr(target_context, 'target_locked', False)
            }

        # 距离和检测信息
        battle_info["distance_info"] = {
            "last_check_distance": auto_battle_context.last_check_distance,
            "without_distance_times": auto_battle_context.without_distance_times,
            "with_distance_times": auto_battle_context.with_distance_times
        }

        # 检查间隔信息
        battle_info["check_intervals"] = {
            "chain": auto_battle_context._check_chain_interval,
            "quick": auto_battle_context._check_quick_interval,
            "end": auto_battle_context._check_end_interval,
            "distance": auto_battle_context._check_distance_interval
        }

    return battle_info


@router.get("/battle-state/detailed", summary="获取详细战斗状态信息")
def get_battle_state_with_metrics(ctx: ZContext = Depends(get_ctx)):
    """
    获取详细的战斗状态信息，包括性能指标和系统状态

    ## 功能描述
    提供比基础战斗状态更详细的信息，包括性能指标、系统状态和调试信息，主要用于开发和调试。

    ## 返回数据
    - **battle_state**: 详细战斗状态信息
      - **is_in_battle**: 是否在战斗中
      - **current_action**: 当前动作
      - **agent_info**: 代理信息
      - **dodge_info**: 闪避信息
      - **target_info**: 目标信息
      - **distance_info**: 距离检测信息
      - **check_intervals**: 检查间隔配置
    - **performance_metrics**: 性能指标
      - **timestamp**: 时间戳
      - **context_running**: 上下文运行状态
      - **task_details**: 任务详细信息
      - **config_info**: 配置信息
    - **last_update**: 最后更新时间
    - **api_version**: API版本

    ## 错误码
    - **DETAILED_STATE_FAILED**: 获取详细状态失败

    ## 使用场景
    - 开发调试
    - 性能分析
    - 系统监控
    - 故障排查

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/battle-state/detailed")
    detailed_state = response.json()
    print(f"战斗状态: {detailed_state['battle_state']['is_in_battle']}")
    print(f"运行任务数: {detailed_state['performance_metrics']['running_tasks']}")
    ```
    """
    try:
        # 收集基础战斗状态
        battle_info = _collect_battle_state_info(ctx)

        # 收集性能指标
        performance_metrics = _collect_battle_performance_metrics(ctx)

        # 组合详细状态信息
        detailed_state = {
            "battle_state": battle_info,
            "performance_metrics": performance_metrics,
            "last_update": datetime.now().isoformat(),
            "api_version": "v1"
        }

        return detailed_state

    except Exception as e:
        log.error(f"获取详细战斗状态失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "DETAILED_STATE_FAILED",
                    "message": f"获取详细战斗状态失败: {str(e)}"
                }
            }
        )


@router.get("/system-status", summary="获取系统状态")
def get_system_status(ctx: ZContext = Depends(get_ctx)):
    """
    获取战斗助手系统的整体状态

    ## 功能描述
    提供战斗助手系统的整体健康状况检查，包括配置状态、任务状态和系统组件状态。

    ## 返回数据
    - **healthy**: 系统是否健康
    - **timestamp**: 检查时间戳
    - **context_status**: 上下文状态
      - **is_running**: 是否运行中
      - **instance_idx**: 实例索引
    - **task_manager**: 任务管理器状态
      - **total_tasks**: 总任务数
      - **running_tasks**: 运行中任务数
      - **pending_tasks**: 等待中任务数
      - **completed_tasks**: 已完成任务数
      - **failed_tasks**: 失败任务数
    - **configuration**: 配置状态
      - **battle_assistant_loaded**: 战斗助手配置是否加载
      - **auto_op_available**: 自动操作是否可用
      - **model_config_loaded**: 模型配置是否加载
      - **game_config_loaded**: 游戏配置是否加载
    - **battle_assistant_config**: 战斗助手配置详情
    - **issues** (可选): 发现的问题列表

    ## 健康检查标准
    - 无失败任务
    - 配置正确加载
    - 系统组件正常运行

    ## 使用场景
    - 系统监控
    - 健康检查
    - 故障诊断
    - 运维管理

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/system-status")
    status = response.json()
    print(f"系统健康: {'正常' if status['healthy'] else '异常'}")
    print(f"运行任务: {status['task_manager']['running_tasks']}")
    if not status['healthy'] and 'issues' in status:
        print(f"发现问题: {status['issues']}")
    ```
    """
    try:
        # 收集系统状态
        system_status = {
            "healthy": True,
            "timestamp": datetime.now().isoformat(),
            "context_status": {
                "is_running": ctx.run_context.is_context_running,
                "instance_idx": getattr(ctx, 'current_instance_idx', 0)
            },
            "task_manager": {
                "total_tasks": len(_registry.list_statuses()),
                "running_tasks": len([s for s in _registry.list_statuses() if s.status.value == "running"]),
                "pending_tasks": len([s for s in _registry.list_statuses() if s.status.value == "pending"]),
                "completed_tasks": len([s for s in _registry.list_statuses() if s.status.value == "completed"]),
                "failed_tasks": len([s for s in _registry.list_statuses() if s.status.value == "failed"])
            },
            "configuration": {
                "battle_assistant_loaded": hasattr(ctx, 'battle_assistant_config'),
                "auto_op_available": ctx.auto_op is not None,
                "model_config_loaded": hasattr(ctx, 'model_config'),
                "game_config_loaded": hasattr(ctx, 'game_config')
            }
        }

        # 检查配置状态
        if hasattr(ctx, 'battle_assistant_config'):
            config = ctx.battle_assistant_config
            system_status["battle_assistant_config"] = {
                "use_gpu": config.use_gpu,
                "screenshot_interval": config.screenshot_interval,
                "gamepad_type": config.gamepad_type,
                "auto_battle_config": getattr(config, 'auto_battle_config', None),
                "dodge_assistant_config": getattr(config, 'dodge_assistant_config', None)
            }

        # 检查是否有错误状态
        failed_tasks = [s for s in _registry.list_statuses() if s.status.value == "failed"]
        if failed_tasks:
            system_status["healthy"] = False
            system_status["issues"] = [f"任务失败: {task.runId}" for task in failed_tasks]

        return system_status

    except Exception as e:
        log.error(f"获取系统状态失败: {str(e)}", exc_info=True)
        return {
            "healthy": False,
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "message": "系统状态检查失败"
        }

# ============================================================================
# WebSocket实时通信支持函数
# ============================================================================

def start_battle_state_monitor(ctx: ZContext):
    """
    启动战斗状态监控，定期广播战斗状态更新
    """
    import threading
    import time

    def monitor_loop():
        """战斗状态监控循环"""
        last_state = None

        while ctx.run_context.is_context_running:
            try:
                # 获取当前战斗状态
                current_state = _get_current_battle_state(ctx)

                # 只有状态发生变化时才广播
                if current_state != last_state:
                    broadcast_battle_assistant_event(
                        BattleAssistantEventType.BATTLE_STATE_CHANGED,
                        current_state
                    )
                    last_state = current_state

                # 等待一段时间再检查
                time.sleep(1.0)  # 每秒检查一次

            except Exception as e:
                log.error(f"战斗状态监控错误: {str(e)}", exc_info=True)
                broadcast_battle_assistant_event(
                    BattleAssistantEventType.ERROR_OCCURRED,
                    {
                        "message": f"战斗状态监控错误: {str(e)}",
                        "details": {"error_type": "monitor_error"}
                    }
                )
                time.sleep(5.0)  # 错误时等待更长时间

    # 在后台线程中启动监控
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()


def _get_current_battle_state(ctx: ZContext) -> dict:
    """
    获取当前战斗状态的内部函数
    """
    is_in_battle = False
    current_action = None
    enemies_detected = 0
    performance_metrics = {}

    # 如果有自动战斗操作器在运行，获取详细状态
    if ctx.auto_op is not None:
        auto_battle_context = ctx.auto_op.auto_battle_context
        is_in_battle = auto_battle_context.last_check_in_battle

        # 获取当前动作
        if hasattr(ctx.auto_op, 'state_recorders') and ctx.auto_op.state_recorders:
            latest_state = None
            latest_time = 0

            for recorder in ctx.auto_op.state_recorders.values():
                if recorder.last_record_time > 0:  # 检查是否有有效的记录时间
                    if recorder.last_record_time > latest_time:
                        latest_time = recorder.last_record_time
                        latest_state = recorder.state_name

            if latest_state:
                current_action = latest_state

        # 收集性能指标
        performance_metrics = {
            "context_running": ctx.run_context.is_context_running,
            "running_tasks": len(_registry.list_statuses()),
            "last_check_distance": getattr(auto_battle_context, 'last_check_distance', 0),
            "without_distance_times": getattr(auto_battle_context, 'without_distance_times', 0),
            "with_distance_times": getattr(auto_battle_context, 'with_distance_times', 0)
        }

    return {
        "is_in_battle": is_in_battle,
        "current_action": current_action,
        "enemies_detected": enemies_detected,
        "last_update": datetime.now().isoformat(),
        "performance_metrics": performance_metrics
    }


@router.get("/detailed-battle-state", response_model=DetailedBattleState, summary="获取详细战斗状态")
def get_detailed_battle_state_with_records(ctx: ZContext = Depends(get_ctx)):
    """
    获取详细的战斗状态信息，包括状态记录器和任务信息

    ## 功能描述
    返回完整的战斗状态信息，包括所有状态记录器的数据和当前运行任务的详细信息。
    主要用于支持GUI中的实时状态显示功能。

    ## 返回数据
    - **basic_state**: 基本战斗状态信息- **state_records**: 所有状态记录器的详细信息列表
    - **current_task**: 当前运行任务的信息
    - **auto_op_running**: 自动操作器是否运行中

    ## 状态记录信息
    - **state_name**: 状态名称
    - **trigger_time**: 触发时间戳
    - **last_record_time**: 最后记录时间戳
    - **value**: 状态值
    - **time_diff**: 距离现在的时间差（秒）

    ## 任务信息
    - **trigger_display**: 触发器显示文本
    - **expr_display**: 条件集显示文本
    - **duration**: 任务持续时间（秒）
    - **is_running**: 是否正在运行

    ## WebSocket事件
    状态变化时会自动通过WebSocket广播detailed_battle_state_changed事件

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/detailed-battle-state")
    state = response.json()
    print(f"自动操作器运行: {state['auto_op_running']}")
    print(f"状态记录数量: {len(state['state_records'])}")
    if state['current_task']:
        print(f"当前任务: {state['current_task']['trigger_display']}")
    ```
    """
    try:
        import time

        # 获取基本战斗状态
        basic_state = get_battle_state(ctx)

        # 初始化返回数据
        state_records = []
        current_task = None
        auto_op_running = False

        # 如果有自动战斗操作器在运行，获取详细状态
        if ctx.auto_op is not None:
            # 更准确地判断auto_op是否在运行
            auto_op_running = bool(ctx.auto_op.is_running or (ctx.run_context.is_context_running and hasattr(ctx.auto_op, 'state_recorders') and bool(ctx.auto_op.state_recorders)))

            # 即使auto_op.is_running为False，如果上下文在运行且有state_recorders，也应该获取状态
            should_get_state = auto_op_running or (ctx.run_context.is_context_running and hasattr(ctx.auto_op, 'state_recorders'))

            if should_get_state:
                # 获取状态记录器信息
                now = time.time()

                # 尝试获取usage_states，如果失败则使用所有state_recorders
                try:
                    states = ctx.auto_op.get_usage_states()
                    states = sorted(states)
                    state_recorders = sorted([i for i in ctx.auto_op.state_recorders.values()
                                            if i.state_name in states],
                                           key=lambda x: x.state_name)
                except:
                    # 如果get_usage_states失败，直接使用所有state_recorders
                    state_recorders = sorted(ctx.auto_op.state_recorders.values(),
                                           key=lambda x: x.state_name)

                for recorder in state_recorders:
                    if recorder.last_record_time == -1:
                        continue
                    if (recorder.last_record_time == 0 and
                        (recorder.state_name.startswith('前台-') or
                         recorder.state_name.startswith('后台-'))):
                        continue

                    time_diff = now - recorder.last_record_time
                    if time_diff > 999:
                        time_diff = 999

                    state_records.append(StateRecordInfo(
                        state_name=recorder.state_name,
                        trigger_time=recorder.last_record_time,
                        last_record_time=recorder.last_record_time,
                        value=recorder.last_value,
                        time_diff=time_diff
                    ))

                # 获取当前任务信息
                running_task = getattr(ctx.auto_op, 'running_task', None)
                if running_task is not None:
                    duration = _calc_task_duration(ctx.auto_op, running_task, now)

                    current_task = TaskInfo(
                        trigger_display=running_task.trigger_display,
                        expr_display=running_task.expr_display,
                        duration=round(duration, 4),
                        is_running=True
                    )

        detailed_state = DetailedBattleState(
            basic_state=basic_state,
            state_records=state_records,
            current_task=current_task,
            auto_op_running=bool(auto_op_running)  # 确保是布尔值
        )

        # 广播详细状态更新事件
        if hasattr(ctx, '_battle_assistant_bridge'):
            bridge = getattr(ctx, '_battle_assistant_bridge')
            bridge.broadcast_battle_state({
                "auto_op_running": auto_op_running,
                "state_records_count": len(state_records),
                "has_current_task": current_task is not None,
                "last_update": datetime.now().isoformat()
            })

        return detailed_state

    except Exception as e:
        # 如果获取详细状态失败，返回基本状态
        log.error(f"获取详细战斗状态失败: {str(e)}", exc_info=True)

        # 广播错误事件
        broadcast_battle_assistant_event(
            BattleAssistantEventType.ERROR_OCCURRED,
            {
                "message": f"获取详细战斗状态失败: {str(e)}",
                "details": {"error_type": "detailed_battle_state_error"}
            }
        )

        return DetailedBattleState(
            basic_state=BattleState(
                is_in_battle=False,
                current_action=None,
                enemies_detected=0,
                last_update=datetime.now(),
                performance_metrics={"error": str(e)}
            ),
            state_records=[],
            current_task=None,
            auto_op_running=False
        )


@router.get("/state-records", response_model=List[StateRecordInfo], summary="获取状态记录列表")
def get_state_records(ctx: ZContext = Depends(get_ctx)) -> List[StateRecordInfo]:
    """
    获取当前所有状态记录器的信息

    ## 功能描述
    返回自动战斗操作器中所有状态记录器的详细信息，用于实时监控战斗状态。

    ## 返回数据
    状态记录信息列表，每个记录包含：
    - **state_name**: 状态名称
    - **trigger_time**: 触发时间戳
    - **last_record_time**: 最后记录时间戳
    - **value**: 状态值
    - **time_diff**: 距离现在的时间差（秒）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/state-records")
    records = response.json()
    for record in records:
        print(f"状态: {record['state_name']}, 值: {record['value']}, 时间差: {record['time_diff']}s")
    ```
    """
    try:
        import time

        state_records = []

        if ctx.auto_op is not None and ctx.auto_op.is_running:
            now = time.time()
            states = ctx.auto_op.get_usage_states()
            states = sorted(states)

            state_recorders = sorted([i for i in ctx.auto_op.state_recorders.values()
                                    if i.state_name in states],
                                   key=lambda x: x.state_name)

            for recorder in state_recorders:
                if recorder.last_record_time == -1:
                    continue
                if (recorder.last_record_time == 0 and
                    (recorder.state_name.startswith('前台-') or
                     recorder.state_name.startswith('后台-'))):
                    continue

                time_diff = now - recorder.last_record_time
                if time_diff > 999:
                    time_diff = 999

                state_records.append(StateRecordInfo(
                    state_name=recorder.state_name,
                    trigger_time=recorder.last_record_time,
                    last_record_time=recorder.last_record_time,
                    value=recorder.last_value,
                    time_diff=time_diff
                ))

        return state_records

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "STATE_RECORDS_FETCH_FAILED",
                    "message": f"获取状态记录失败: {str(e)}"
                }
            }
        )


@router.get("/current-task", response_model=Optional[TaskInfo], summary="获取当前任务信息")
def get_current_task(ctx: ZContext = Depends(get_ctx)) -> Optional[TaskInfo]:
    """
    获取当前运行任务的详细信息

    ## 功能描述
    返回自动战斗操作器当前正在执行的任务信息，包括触发器、条件集和持续时间。

    ## 返回数据
    如果有任务在运行，返回任务信息：
    - **trigger_display**: 触发器显示文本
    - **expr_display**: 条件集显示文本
    - **duration**: 任务持续时间（秒）
    - **is_running**: 是否正在运行

    如果没有任务在运行，返回null

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/current-task")
    task = response.json()
    if task:
        print(f"当前任务: {task['trigger_display']}")
        print(f"持续时间: {task['duration']}秒")
    else:
        print("没有任务在运行")
    ```
    """
    try:
        import time

        # 检查auto_op是否存在且有运行任务
        if ctx.auto_op is not None:
            # 即使is_running为False，如果上下文在运行且有running_task，也应该返回任务信息
            should_check_task = ctx.auto_op.is_running or (ctx.run_context.is_context_running and hasattr(ctx.auto_op, 'running_task'))

            if should_check_task:
                running_task = getattr(ctx.auto_op, 'running_task', None)
                if running_task is not None:
                    now = time.time()
                    duration = _calc_task_duration(ctx.auto_op, running_task, now)

                    return TaskInfo(
                        trigger_display=running_task.trigger_display,
                        expr_display=running_task.expr_display,
                        duration=round(duration, 4),
                        is_running=True
                    )

        return None

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CURRENT_TASK_FETCH_FAILED",
                    "message": f"获取当前任务信息失败: {str(e)}"
                }
            }
        )


# ============================================================================
# 统一控制接口端点
# ============================================================================

from zzz_od.api.battle_assistant_controllers import auto_battle_controller, dodge_controller, operation_debug_controller
from zzz_od.api.models import ControlResponse, StatusResponse, LogReplayResponse


@router.post("/auto-battle/start", response_model=ControlResponse, summary="启动自动战斗（统一接口）")
async def start_auto_battle_unified(ctx: ZContext = Depends(get_ctx)):
    """
    启动自动战斗任务（统一控制接口）

    ## 功能描述
    使用统一控制接口启动自动战斗任务，支持幂等性处理和标准化响应格式。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 运行实例ID
    - **capabilities**: 模块能力标识
      - **canPause**: 是否支持暂停（true）
      - **canResume**: 是否支持恢复（true）

    ## 幂等性
    如果模块已在运行，返回当前运行的runId而不是错误

    ## WebSocket事件
    启动后会通过统一WebSocket事件系统发送：
    - **status_update**: 状态更新事件
    - **task_started**: 任务开始事件

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/auto-battle/start")
    result = response.json()
    print(f"运行ID: {result['runId']}")
    print(f"支持暂停: {result['capabilities']['canPause']}")
    ```
    """
    return await auto_battle_controller.start(ctx)


@router.post("/auto-battle/stop", response_model=ControlResponse, summary="停止自动战斗（统一接口）")
async def stop_auto_battle_unified():
    """
    停止自动战斗任务（统一控制接口）

    ## 功能描述
    使用统一控制接口停止自动战斗任务，支持幂等性处理。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **capabilities**: 模块能力标识

    ## 幂等性
    如果模块未在运行，返回成功状态而不是错误

    ## WebSocket事件
    停止后会通过统一WebSocket事件系统发送：
    - **status_update**: 状态更新事件
    - **task_completed**: 任务完成事件

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/auto-battle/stop")
    result = response.json()
    print(f"停止结果: {result['message']}")
    ```
    """
    return await auto_battle_controller.stop()


@router.post("/auto-battle/pause", response_model=ControlResponse, summary="暂停自动战斗（统一接口）")
async def pause_auto_battle_unified():
    """
    暂停自动战斗任务（统一控制接口）

    ## 功能描述
    暂停当前运行的自动战斗任务。自动战斗模块支持暂停功能。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **capabilities**: 模块能力标识

    ## 错误码
    - **405**: 模块不支持暂停操作
    - **501**: 暂停功能尚未实现

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/auto-battle/pause")
    result = response.json()
    print(f"暂停结果: {result['message']}")
    ```
    """
    return await auto_battle_controller.pause()


@router.post("/auto-battle/resume", response_model=ControlResponse, summary="恢复自动战斗（统一接口）")
async def resume_auto_battle_unified():
    """
    恢复自动战斗任务（统一控制接口）

    ## 功能描述
    恢复已暂停的自动战斗任务。自动战斗模块支持恢复功能。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **capabilities**: 模块能力标识

    ## 错误码
    - **405**: 模块不支持恢复操作
    - **501**: 恢复功能尚未实现

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/auto-battle/resume")
    result = response.json()
    print(f"恢复结果: {result['message']}")
    ```
    """
    return await auto_battle_controller.resume()


@router.get("/auto-battle/status", response_model=StatusResponse, summary="获取自动战斗状态（统一接口）")
async def get_auto_battle_status_unified():
    """
    获取自动战斗模块状态（统一控制接口）

    ## 功能描述
    获取自动战斗模块的当前运行状态，包括运行状态、上下文状态和能力信息。

    ## 返回数据
    - **is_running**: 是否正在运行
    - **context_state**: 上下文状态（idle | running | paused）
    - **running_tasks**: 运行中的任务数量（可选）
    - **message**: 状态消息（可选）
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识
      - **canPause**: 是否支持暂停（true）
      - **canResume**: 是否支持恢复（true）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/auto-battle/status")
    status = response.json()
    print(f"运行状态: {status['is_running']}")
    print(f"上下文状态: {status['context_state']}")
    print(f"支持暂停: {status['capabilities']['canPause']}")
    ```
    """
    return await auto_battle_controller.status()


@router.get("/auto-battle/logs", response_model=LogReplayResponse, summary="获取自动战斗运行日志")
async def auto_battle_logs(
    runId: str = None,
    tail: int = 1000
) -> LogReplayResponse:
    """
    获取自动战斗运行日志回放

    ## 功能描述
    获取指定runId的自动战斗运行日志，支持回放最近的日志记录。所有时间戳使用UTC ISO8601格式。

    ## 查询参数
    - **runId** (可选): 运行ID，不提供则使用当前运行的ID
    - **tail** (可选): 返回最后N条日志，默认1000，最大2000

    ## 返回数据
    - **logs**: 日志条目列表
      - **timestamp**: 时间戳，UTC ISO8601格式（2025-09-20T12:34:56.789Z）
      - **level**: 日志级别 (debug | info | warning | error)
      - **message**: 日志消息
      - **runId**: 运行ID
      - **module**: 模块名称
      - **seq**: 序列号
      - **extra**: 额外信息
    - **total_count**: 返回的日志条数
    - **runId**: 查询的运行ID
    - **module**: 模块名称
    - **has_more**: 是否还有更多日志（当前实现中始终为false）
    - **message**: 响应消息

    ## 默认策略
    - 当runId不存在时，返回空日志列表和说明消息
    - 当无日志记录时，返回"暂无日志记录"消息
    - 日志条数限制在2000条以内

    ## 使用示例
    ```python
    import requests

    # 获取当前运行的最新1000条日志
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/auto-battle/logs")

    # 获取指定runId的最新500条日志
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/auto-battle/logs?runId=abc123&tail=500")

    logs = response.json()
    for log in logs['logs']:
        print(f"[{log['timestamp']}] {log['level'].upper()}: {log['message']}")
    ```
    """
    return await auto_battle_controller.get_logs(runId, tail)


@router.post("/dodge/start", response_model=ControlResponse, summary="启动闪避助手（统一接口）")
async def start_dodge_unified(ctx: ZContext = Depends(get_ctx)):
    """
    启动闪避助手任务（统一控制接口）

    ## 功能描述
    使用统一控制接口启动闪避助手任务，支持幂等性处理和标准化响应格式。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 运行实例ID
    - **capabilities**: 模块能力标识
      - **canPause**: 是否支持暂停（false）
      - **canResume**: 是否支持恢复（false）

    ## 幂等性
    如果模块已在运行，返回当前运行的runId而不是错误

    ## WebSocket事件
    启动后会通过统一WebSocket事件系统发送：
    - **status_update**: 状态更新事件
    - **task_started**: 任务开始事件

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/dodge/start")
    result = response.json()
    print(f"运行ID: {result['runId']}")
    print(f"支持暂停: {result['capabilities']['canPause']}")
    ```
    """
    return await dodge_controller.start(ctx)


@router.post("/dodge/stop", response_model=ControlResponse, summary="停止闪避助手（统一接口）")
async def stop_dodge_unified():
    """
    停止闪避助手任务（统一控制接口）

    ## 功能描述
    使用统一控制接口停止闪避助手任务，支持幂等性处理。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **capabilities**: 模块能力标识

    ## 幂等性
    如果模块未在运行，返回成功状态而不是错误

    ## WebSocket事件
    停止后会通过统一WebSocket事件系统发送：
    - **status_update**: 状态更新事件
    - **task_completed**: 任务完成事件

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/dodge/stop")
    result = response.json()
    print(f"停止结果: {result['message']}")
    ```
    """
    return await dodge_controller.stop()


@router.get("/dodge/status", response_model=StatusResponse, summary="获取闪避助手状态（统一接口）")
async def get_dodge_status_unified():
    """
    获取闪避助手模块状态（统一控制接口）

    ## 功能描述
    获取闪避助手模块的当前运行状态，包括运行状态、上下文状态和能力信息。

    ## 返回数据
    - **is_running**: 是否正在运行
    - **context_state**: 上下文状态（idle | running | paused）
    - **running_tasks**: 运行中的任务数量（可选）
    - **message**: 状态消息（可选）
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识
      - **canPause**: 是否支持暂停（false）
      - **canResume**: 是否支持恢复（false）

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/dodge/status")
    status = response.json()
    print(f"运行状态: {status['is_running']}")
    print(f"上下文状态: {status['context_state']}")
    print(f"支持暂停: {status['capabilities']['canPause']}")
    ```
    """
    return await dodge_controller.status()


@router.post("/dodge/pause", response_model=ControlResponse, summary="暂停闪避助手（统一接口）")
async def pause_dodge_unified():
    """
    暂停闪避助手自动化任务

    ## 功能描述
    暂停当前正在运行的闪避助手任务，保持状态以便后续恢复。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/dodge/pause")
    result = response.json()
    print(f"暂停结果: {result['ok']}, 消息: {result['message']}")
    ```
    """
    return await dodge_controller.pause()


@router.post("/dodge/resume", response_model=ControlResponse, summary="恢复闪避助手（统一接口）")
async def resume_dodge_unified():
    """
    恢复闪避助手自动化任务

    ## 功能描述
    恢复之前暂停的闪避助手任务执行。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/battle-assistant/dodge/resume")
    result = response.json()
    print(f"恢复结果: {result['ok']}, 消息: {result['message']}")
    ```
    """
    return await dodge_controller.resume()


@router.get("/dodge/logs", response_model=LogReplayResponse, summary="获取闪避助手运行日志")
async def dodge_logs(
    runId: str = None,
    tail: int = 1000
) -> LogReplayResponse:
    """
    获取闪避助手运行日志回放

    ## 功能描述
    获取指定runId的闪避助手运行日志，支持回放最近的日志记录。所有时间戳使用UTC ISO8601格式。

    ## 查询参数
    - **runId** (可选): 运行ID，不提供则使用当前运行的ID
    - **tail** (可选): 返回最后N条日志，默认1000，最大2000

    ## 返回数据
    - **logs**: 日志条目列表
      - **timestamp**: 时间戳，UTC ISO8601格式（2025-09-20T12:34:56.789Z）
      - **level**: 日志级别 (debug | info | warning | error)
      - **message**: 日志消息
      - **runId**: 运行ID
      - **module**: 模块名称
      - **seq**: 序列号
      - **extra**: 额外信息
    - **total_count**: 返回的日志条数
    - **runId**: 查询的运行ID
    - **module**: 模块名称
    - **has_more**: 是否还有更多日志（当前实现中始终为false）
    - **message**: 响应消息

    ## 默认策略
    - 当runId不存在时，返回空日志列表和说明消息
    - 当无日志记录时，返回"暂无日志记录"消息
    - 日志条数限制在2000条以内

    ## 使用示例
    ```python
    import requests

    # 获取当前运行的最新1000条日志
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/dodge/logs")

    # 获取指定runId的最新500条日志
    response = requests.get("http://localhost:8000/api/v1/battle-assistant/dodge/logs?runId=abc123&tail=500")

    logs = response.json()
    for log in logs['logs']:
        print(f"[{log['timestamp']}] {log['level'].upper()}: {log['message']}")
    ```
    """
    return await dodge_controller.get_logs(runId, tail)


# 为了保持向后兼容性，现有的/run端点内部转发到新的/start端点
# 这些修改将在现有端点的实现中进行
