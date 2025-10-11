from __future__ import annotations

from typing import Dict, Any, Callable

from fastapi import APIRouter, Depends

from zzz_od.api.context_helpers import (
    get_app_config,
    get_app_run_record,
    get_one_dragon_app_config,
)
from zzz_od.api.deps import get_ctx
from zzz_od.api.models import RunIdResponse, ControlResponse, StatusResponse, Capabilities, LogReplayResponse
from zzz_od.api.security import get_api_key_dependency
from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.bridges import attach_run_event_bridge
from zzz_od.api.unified_controller import UnifiedController
from zzz_od.application.commission_assistant.commission_assistant_app import CommissionAssistantApp
from zzz_od.application.commission_assistant import commission_assistant_const
from zzz_od.application.life_on_line.life_on_line_app import LifeOnLineApp
from zzz_od.application.life_on_line import life_on_line_const
from zzz_od.application.game_config_checker.mouse_sensitivity_checker import MouseSensitivityChecker
from zzz_od.application.game_config_checker.predefined_team_checker import PredefinedTeamChecker


router = APIRouter(
    prefix="/api/v1/game-assistant",
    tags=["游戏助手 Game Assistant"],
    dependencies=[Depends(get_api_key_dependency())],
)


_registry = get_global_run_registry()


class CommissionAssistantController(UnifiedController):
    """委托助手统一控制器"""

    def __init__(self):
        super().__init__("commission-assistant")

    def get_capabilities(self) -> Capabilities:
        """委托助手支持暂停/恢复"""
        return Capabilities(canPause=True, canResume=True)

    def create_app_factory(self) -> Callable:
        """创建委托助手应用工厂"""
        def factory():
            ctx = get_ctx()
            return CommissionAssistantApp(ctx)
        return factory


class LifeOnLineController(UnifiedController):
    """拿命验收统一控制器"""

    def __init__(self):
        super().__init__("life-on-line")

    def get_capabilities(self) -> Capabilities:
        """拿命验收支持暂停/恢复"""
        return Capabilities(canPause=True, canResume=True)

    def create_app_factory(self) -> Callable:
        """创建拿命验收应用工厂"""
        def factory():
            ctx = get_ctx()
            return LifeOnLineApp(ctx)
        return factory


# 创建控制器实例
_commission_assistant_controller = CommissionAssistantController()
_life_on_line_controller = LifeOnLineController()


def _run_via_onedragon_with_temp(app_ids: list[str]) -> str:
    """通过一条龙总控运行指定 appId 列表（临时运行清单）。"""
    ctx = get_ctx()
    config = get_one_dragon_app_config(ctx)
    original_temp = config.temp_app_run_list
    config.set_temp_app_run_list(app_ids)
    from zzz_od.application.one_dragon_app.zzz_one_dragon_app import ZOneDragonApp
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


@router.post("/commission-assistant/start", response_model=ControlResponse, summary="启动委托助手")
async def start_commission_assistant():
    """
    启动委托助手自动化任务

    ## 功能描述
    启动委托助手应用，自动完成游戏中的委托任务，包括对话处理、战斗和任务流程。
    支持幂等性操作，重复调用会返回当前运行状态。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 任务运行ID，用于后续状态查询和控制
    - **capabilities**: 模块能力标识

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **CONFIG_ERROR**: 配置错误

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/commission-assistant/start")
    result = response.json()
    print(f"启动结果: {result['message']}")
    print(f"任务ID: {result['runId']}")
    ```
    """
    return await _commission_assistant_controller.start()


@router.post("/commission-assistant/stop", response_model=ControlResponse, summary="停止委托助手")
async def stop_commission_assistant():
    """
    停止委托助手自动化任务

    ## 功能描述
    停止当前运行的委托助手任务。支持幂等性操作，重复调用不会报错。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/commission-assistant/stop")
    result = response.json()
    print(f"停止结果: {result['message']}")
    ```
    """
    return await _commission_assistant_controller.stop()


@router.get("/commission-assistant/status", response_model=StatusResponse, summary="获取委托助手状态")
async def get_commission_assistant_status():
    """
    获取委托助手的运行状态

    ## 功能描述
    返回委托助手的当前运行状态，包括是否运行中、上下文状态等信息。

    ## 返回数据
    - **is_running**: 是否正在运行
    - **context_state**: 上下文状态 (idle | running | paused)
    - **running_tasks**: 运行中的任务数量（可选）
    - **message**: 状态消息
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/game-assistant/commission-assistant/status")
    status = response.json()
    print(f"运行状态: {status['context_state']}")
    print(f"是否运行: {status['is_running']}")
    ```
    """
    return await _commission_assistant_controller.status()


@router.post("/commission-assistant/pause", response_model=ControlResponse, summary="暂停委托助手")
async def pause_commission_assistant():
    """
    暂停委托助手自动化任务

    ## 功能描述
    暂停当前正在运行的委托助手任务，保持状态以便后续恢复。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/commission-assistant/pause")
    result = response.json()
    print(f"暂停结果: {result['ok']}, 消息: {result['message']}")
    ```
    """
    return await _commission_assistant_controller.pause()


@router.post("/commission-assistant/resume", response_model=ControlResponse, summary="恢复委托助手")
async def resume_commission_assistant():
    """
    恢复委托助手自动化任务

    ## 功能描述
    恢复之前暂停的委托助手任务执行。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/commission-assistant/resume")
    result = response.json()
    print(f"恢复结果: {result['ok']}, 消息: {result['message']}")
    ```
    """
    return await _commission_assistant_controller.resume()


@router.get("/commission-assistant/logs", response_model=LogReplayResponse, summary="获取委托助手运行日志")
async def commission_assistant_logs(
    runId: str = None,
    tail: int = 1000
) -> LogReplayResponse:
    """
    获取委托助手运行日志回放

    ## 功能描述
    获取指定runId的委托助手运行日志，支持回放最近的日志记录。所有时间戳使用UTC ISO8601格式。

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
    response = requests.get("http://localhost:8000/api/v1/game-assistant/commission-assistant/logs")

    # 获取指定runId的最新500条日志
    response = requests.get("http://localhost:8000/api/v1/game-assistant/commission-assistant/logs?runId=abc123&tail=500")

    logs = response.json()
    for log in logs['logs']:
        print(f"[{log['timestamp']}] {log['level'].upper()}: {log['message']}")
    ```
    """
    return await _commission_assistant_controller.get_logs(runId, tail)


@router.post("/commission-assistant/run", response_model=RunIdResponse, summary="运行委托助手")
async def run_commission_assistant():
    """
    启动委托助手自动化任务（兼容性端点）

    ## 功能描述
    直接启动委托助手应用，自动完成游戏中的委托任务，包括对话处理、战斗和任务流程。
    不会执行一条龙的完整流程，只运行委托助手本身。

    **注意**: 此端点已废弃，建议使用 `/start` 端点。

    ## 返回数据
    - **runId**: 任务运行ID，用于后续状态查询和控制

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **CONFIG_ERROR**: 配置错误

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/commission-assistant/run")
    task_info = response.json()
    print(f"委托助手任务ID: {task_info['runId']}")
    ```
    """
    # 内部转发到新的start端点
    result = await _commission_assistant_controller.start()
    return RunIdResponse(runId=result.runId)


@router.get("/commission-assistant/config", response_model=Dict[str, Any], summary="获取委托助手配置")
def get_commission_assistant_config() -> Dict[str, Any]:
    """
    获取委托助手的当前配置

    ## 功能描述
    返回委托助手的详细配置信息，包括对话设置、战斗配置和闪避设置。

    ## 返回数据
    - **dialogClickInterval**: 对话点击间隔时间（秒）
    - **storyMode**: 剧情模式设置
    - **dialogOption**: 对话选项配置
    - **dodgeConfig**: 闪避配置名称
    - **dodgeSwitch**: 闪避开关状态
    - **autoBattle**: 自动战斗配置名称
    - **autoBattleSwitch**: 自动战斗开关状态

    ## 错误码
    - **CONFIG_READ_FAILED**: 读取配置失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/game-assistant/commission-assistant/config")
    config = response.json()
    print(f"对话间隔: {config['dialogClickInterval']}秒")
    ```
    """
    ctx = get_ctx()
    config = get_app_config(ctx, app_id=commission_assistant_const.APP_ID)
    return {
        "dialogClickInterval": config.dialog_click_interval,
        "storyMode": config.story_mode,
        "dialogOption": config.dialog_option,
        "dodgeConfig": config.dodge_config,
        "dodgeSwitch": config.dodge_switch,
        "autoBattle": config.auto_battle,
        "autoBattleSwitch": config.auto_battle_switch,
    }


@router.put("/commission-assistant/config", response_model=Dict[str, Any], summary="更新委托助手配置")
def update_commission_assistant_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新委托助手的配置参数

    ## 功能描述
    更新委托助手的配置设置，支持部分更新。只需要提供需要修改的字段。
    配置更新后会通过WebSocket推送给前端，减少轮询请求。

    ## 请求参数
    - **dialogClickInterval** (可选): 对话点击间隔时间，单位秒
    - **storyMode** (可选): 剧情模式设置
    - **dialogOption** (可选): 对话选项配置
    - **dodgeConfig** (可选): 闪避配置名称
    - **dodgeSwitch** (可选): 闪避开关状态，布尔值
    - **autoBattle** (可选): 自动战斗配置名称
    - **autoBattleSwitch** (可选): 自动战斗开关状态，布尔值

    ## 返回数据
    - **message**: 更新成功消息

    ## WebSocket推送
    配置更新后会向 `/ws/v1/game-assistant/config-updates` 推送更新事件

    ## 错误码
    - **CONFIG_UPDATE_FAILED**: 配置更新失败
    - **VALIDATION_ERROR**: 参数验证失败

    ## 使用示例
    ```python
    import requests
    data = {
        "dialogClickInterval": 0.5,
        "autoBattleSwitch": True
    }
    response = requests.put("http://localhost:8000/api/v1/game-assistant/commission-assistant/config", json=data)
    print(response.json()["message"])
    ```
    """
    ctx = get_ctx()
    config = get_app_config(ctx, app_id=commission_assistant_const.APP_ID)

    updated_fields = []

    if "dialogClickInterval" in payload:
        config.dialog_click_interval = float(payload["dialogClickInterval"])
        updated_fields.append("dialogClickInterval")
    if "storyMode" in payload:
        config.story_mode = payload["storyMode"]
        updated_fields.append("storyMode")
    if "dialogOption" in payload:
        config.dialog_option = payload["dialogOption"]
        updated_fields.append("dialogOption")
    if "dodgeConfig" in payload:
        config.dodge_config = payload["dodgeConfig"]
        updated_fields.append("dodgeConfig")
    if "dodgeSwitch" in payload:
        config.dodge_switch = payload["dodgeSwitch"]
        updated_fields.append("dodgeSwitch")
    if "autoBattle" in payload:
        config.auto_battle = payload["autoBattle"]
        updated_fields.append("autoBattle")
    if "autoBattleSwitch" in payload:
        config.auto_battle_switch = payload["autoBattleSwitch"]
        updated_fields.append("autoBattleSwitch")

    # 推送配置更新事件到WebSocket
    if updated_fields:
        import asyncio
        from zzz_od.api.ws import manager

        def broadcast_config_update():
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(manager.broadcast_json(
                        "game-assistant:config-updates",
                        {
                            "type": "commission_assistant_config_updated",
                            "component": "commission-assistant",
                            "updated_fields": updated_fields,
                            "config": {
                                "dialogClickInterval": config.dialog_click_interval,
                                "storyMode": config.story_mode,
                                "dialogOption": config.dialog_option,
                                "dodgeConfig": config.dodge_config,
                                "dodgeSwitch": config.dodge_switch,
                                "autoBattle": config.auto_battle,
                                "autoBattleSwitch": config.auto_battle_switch,
                            }
                        }
                    ))
            except Exception:
                pass  # WebSocket推送失败不影响配置更新

        broadcast_config_update()

    return {"message": "Configuration updated successfully"}


# -------- Life on Line (拿命验收) --------


@router.post("/life-on-line/start", response_model=ControlResponse, summary="启动拿命验收")
async def start_life_on_line():
    """
    启动拿命验收自动化任务

    ## 功能描述
    启动拿命验收应用，自动完成游戏中的拿命验收挑战，包括队伍选择和战斗流程。
    支持幂等性操作，重复调用会返回当前运行状态。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 任务运行ID，用于后续状态查询和控制
    - **capabilities**: 模块能力标识

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **CONFIG_ERROR**: 配置错误
    - **DAILY_LIMIT_REACHED**: 已达到每日运行次数限制

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/life-on-line/start")
    result = response.json()
    print(f"启动结果: {result['message']}")
    print(f"任务ID: {result['runId']}")
    ```
    """
    return await _life_on_line_controller.start()


@router.post("/life-on-line/stop", response_model=ControlResponse, summary="停止拿命验收")
async def stop_life_on_line():
    """
    停止拿命验收自动化任务

    ## 功能描述
    停止当前运行的拿命验收任务。支持幂等性操作，重复调用不会报错。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/life-on-line/stop")
    result = response.json()
    print(f"停止结果: {result['message']}")
    ```
    """
    return await _life_on_line_controller.stop()


@router.get("/life-on-line/status", response_model=StatusResponse, summary="获取拿命验收状态")
async def get_life_on_line_status():
    """
    获取拿命验收的运行状态

    ## 功能描述
    返回拿命验收的当前运行状态，包括是否运行中、上下文状态等信息。

    ## 返回数据
    - **is_running**: 是否正在运行
    - **context_state**: 上下文状态 (idle | running | paused)
    - **running_tasks**: 运行中的任务数量（可选）
    - **message**: 状态消息
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/game-assistant/life-on-line/status")
    status = response.json()
    print(f"运行状态: {status['context_state']}")
    print(f"是否运行: {status['is_running']}")
    ```
    """
    return await _life_on_line_controller.status()


@router.post("/life-on-line/pause", response_model=ControlResponse, summary="暂停拿命验收")
async def pause_life_on_line():
    """
    暂停拿命验收自动化任务

    ## 功能描述
    暂停当前正在运行的拿命验收任务，保持状态以便后续恢复。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/life-on-line/pause")
    result = response.json()
    print(f"暂停结果: {result['ok']}, 消息: {result['message']}")
    ```
    """
    return await _life_on_line_controller.pause()


@router.post("/life-on-line/resume", response_model=ControlResponse, summary="恢复拿命验收")
async def resume_life_on_line():
    """
    恢复拿命验收自动化任务

    ## 功能描述
    恢复之前暂停的拿命验收任务执行。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息
    - **runId**: 当前运行ID（如果有）
    - **capabilities**: 模块能力标识

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/life-on-line/resume")
    result = response.json()
    print(f"恢复结果: {result['ok']}, 消息: {result['message']}")
    ```
    """
    return await _life_on_line_controller.resume()


@router.get("/life-on-line/logs", response_model=LogReplayResponse, summary="获取拿命验收运行日志")
async def life_on_line_logs(
    runId: str = None,
    tail: int = 1000
) -> LogReplayResponse:
    """
    获取拿命验收运行日志回放

    ## 功能描述
    获取指定runId的拿命验收运行日志，支持回放最近的日志记录。所有时间戳使用UTC ISO8601格式。

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
    response = requests.get("http://localhost:8000/api/v1/game-assistant/life-on-line/logs")

    # 获取指定runId的最新500条日志
    response = requests.get("http://localhost:8000/api/v1/game-assistant/life-on-line/logs?runId=abc123&tail=500")

    logs = response.json()
    for log in logs['logs']:
        print(f"[{log['timestamp']}] {log['level'].upper()}: {log['message']}")
    ```
    """
    return await _life_on_line_controller.get_logs(runId, tail)


@router.post("/life-on-line/run", response_model=RunIdResponse, summary="运行拿命验收")
async def run_life_on_line():
    """
    启动拿命验收自动化任务（兼容性端点）

    ## 功能描述
    直接启动拿命验收应用，自动完成游戏中的拿命验收挑战，包括队伍选择和战斗流程。
    不会执行一条龙的完整流程，只运行拿命验收本身。

    **注意**: 此端点已废弃，建议使用 `/start` 端点。

    ## 返回数据
    - **runId**: 任务运行ID，用于后续状态查询和控制

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **CONFIG_ERROR**: 配置错误
    - **DAILY_LIMIT_REACHED**: 已达到每日运行次数限制

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/life-on-line/run")
    task_info = response.json()
    print(f"拿命验收任务ID: {task_info['runId']}")
    ```
    """
    # 内部转发到新的start端点
    result = await _life_on_line_controller.start()
    return RunIdResponse(runId=result.runId)


@router.get("/life-on-line/config", response_model=Dict[str, Any], summary="获取拿命验收配置")
def get_life_on_line_config() -> Dict[str, Any]:
    """
    获取拿命验收的当前配置

    ## 功能描述
    返回拿命验收的详细配置信息，包括每日计划次数和预设队伍索引。

    ## 返回数据
    - **dailyPlanTimes**: 每日计划运行次数
    - **predefinedTeamIdx**: 预设队伍索引 (-1表示游戏内配队)

    ## 错误码
    - **CONFIG_READ_FAILED**: 读取配置失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/game-assistant/life-on-line/config")
    config = response.json()
    print(f"每日次数: {config['dailyPlanTimes']}")
    print(f"队伍索引: {config['predefinedTeamIdx']}")
    ```
    """
    ctx = get_ctx()
    config = get_app_config(ctx, app_id=life_on_line_const.APP_ID)
    return {
        "dailyPlanTimes": config.daily_plan_times,
        "predefinedTeamIdx": config.predefined_team_idx,
    }


@router.put("/life-on-line/config", response_model=Dict[str, Any], summary="更新拿命验收配置")
def update_life_on_line_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新拿命验收的配置参数

    ## 功能描述
    更新拿命验收的配置设置，支持部分更新。只需要提供需要修改的字段。
    配置更新后会通过WebSocket推送给前端。

    ## 请求参数
    - **dailyPlanTimes** (可选): 每日计划运行次数，整数
    - **predefinedTeamIdx** (可选): 预设队伍索引，-1表示游戏内配队

    ## 返回数据
    - **message**: 更新成功消息

    ## WebSocket推送
    配置更新后会向 `/ws/v1/game-assistant/config-updates` 推送更新事件

    ## 错误码
    - **CONFIG_UPDATE_FAILED**: 配置更新失败
    - **VALIDATION_ERROR**: 参数验证失败

    ## 使用示例
    ```python
    import requests
    data = {
        "dailyPlanTimes": 3,
        "predefinedTeamIdx": 1
    }
    response = requests.put("http://localhost:8000/api/v1/game-assistant/life-on-line/config", json=data)
    print(response.json()["message"])
    ```
    """
    ctx = get_ctx()
    config = get_app_config(ctx, app_id=life_on_line_const.APP_ID)

    updated_fields = []

    if "dailyPlanTimes" in payload:
        config.daily_plan_times = int(payload["dailyPlanTimes"])
        updated_fields.append("dailyPlanTimes")
    if "predefinedTeamIdx" in payload:
        config.predefined_team_idx = int(payload["predefinedTeamIdx"])
        updated_fields.append("predefinedTeamIdx")

    # 推送配置更新事件到WebSocket
    if updated_fields:
        import asyncio
        from zzz_od.api.ws import manager

        def broadcast_config_update():
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(manager.broadcast_json(
                        "game-assistant:config-updates",
                        {
                            "type": "life_on_line_config_updated",
                            "component": "life-on-line",
                            "updated_fields": updated_fields,
                            "config": {
                                "dailyPlanTimes": config.daily_plan_times,
                                "predefinedTeamIdx": config.predefined_team_idx,
                            }
                        }
                    ))
            except Exception:
                pass  # WebSocket推送失败不影响配置更新

        broadcast_config_update()

    return {"message": "Configuration updated successfully"}


@router.get("/life-on-line/record", response_model=Dict[str, Any], summary="获取拿命验收运行记录")
def get_life_on_line_record() -> Dict[str, Any]:
    """
    获取拿命验收的运行记录

    ## 功能描述
    返回拿命验收的历史运行记录，包括每日运行次数和完成状态。

    ## 返回数据
    - **dailyRunTimes**: 今日已运行次数
    - **isFinishedByTimes**: 是否已按次数完成

    ## 错误码
    - **RECORD_READ_FAILED**: 读取记录失败

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/game-assistant/life-on-line/record")
    record = response.json()
    print(f"今日运行: {record['dailyRunTimes']}次")
    print(f"是否完成: {record['isFinishedByTimes']}")
    ```
    """
    ctx = get_ctx()
    record = get_app_run_record(ctx, app_id=life_on_line_const.APP_ID)
    return {
        "dailyRunTimes": record.daily_run_times,
        "isFinishedByTimes": record.is_finished_by_times(),
    }


# -------- Mouse Sensitivity Checker (鼠标校准) --------


@router.post("/mouse-sensitivity-checker/run", response_model=RunIdResponse, summary="运行鼠标灵敏度检查器")
async def run_mouse_sensitivity_checker():
    """
    启动鼠标灵敏度校准任务

    ## 功能描述
    直接启动鼠标灵敏度检查器，自动检测和校准游戏中的鼠标灵敏度设置，确保操作精度。
    不会执行一条龙的完整流程，只运行鼠标校准本身。

    ## 返回数据
    - **runId**: 任务运行ID，用于后续状态查询和控制

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **MOUSE_NOT_DETECTED**: 未检测到鼠标

    ## 注意事项
    - 运行期间请勿移动鼠标
    - 确保游戏处于前台状态

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/mouse-sensitivity-checker/run")
    task_info = response.json()
    print(f"鼠标校准任务ID: {task_info['runId']}")
    ```
    """
    run_id = _start_app_run(lambda c: MouseSensitivityChecker(c))
    return RunIdResponse(runId=run_id)


# -------- Predefined Team Checker (预备编队识别) --------


@router.post("/predefined-team-checker/run", response_model=RunIdResponse, summary="运行预设队伍检查器")
async def run_predefined_team_checker():
    """
    启动预设队伍识别任务

    ## 功能描述
    直接启动预设队伍检查器，自动识别和验证游戏中的预设队伍配置，确保队伍设置正确。
    不会执行一条龙的完整流程，只运行队伍检查本身。

    ## 返回数据
    - **runId**: 任务运行ID，用于后续状态查询和控制

    ## 错误码
    - **TASK_START_FAILED**: 任务启动失败
    - **TEAM_NOT_FOUND**: 未找到预设队伍

    ## 注意事项
    - 确保游戏处于队伍配置界面
    - 运行前请先配置好预设队伍

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/game-assistant/predefined-team-checker/run")
    task_info = response.json()
    print(f"队伍检查任务ID: {task_info['runId']}")
    ```
    """
    run_id = _start_app_run(lambda c: PredefinedTeamChecker(c))
    return RunIdResponse(runId=run_id)
