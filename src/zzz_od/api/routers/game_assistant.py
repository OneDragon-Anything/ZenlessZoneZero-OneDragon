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
    tags=["游戏助手 Game Assistant"],
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


@router.post("/commission-assistant/run", response_model=RunIdResponse, summary="运行委托助手")
async def run_commission_assistant():
    """
    启动委托助手自动化任务

    ## 功能描述
    启动委托助手，自动完成游戏中的委托任务，包括对话处理、战斗和任务流程。

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
    run_id = _run_via_onedragon_with_temp(["commission_assistant"])
    return RunIdResponse(runId=run_id)


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


@router.put("/commission-assistant/config", response_model=Dict[str, Any], summary="更新委托助手配置")
def update_commission_assistant_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新委托助手的配置参数

    ## 功能描述
    更新委托助手的配置设置，支持部分更新。只需要提供需要修改的字段。

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


@router.post("/life-on-line/run", response_model=RunIdResponse, summary="运行拿命验收")
async def run_life_on_line():
    """
    启动拿命验收自动化任务

    ## 功能描述
    启动拿命验收任务，自动完成游戏中的拿命验收挑战，包括队伍选择和战斗流程。

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
    run_id = _run_via_onedragon_with_temp(["life_on_line"])
    return RunIdResponse(runId=run_id)


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
    config = ctx.life_on_line_config
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

    ## 请求参数
    - **dailyPlanTimes** (可选): 每日计划运行次数，整数
    - **predefinedTeamIdx** (可选): 预设队伍索引，-1表示游戏内配队

    ## 返回数据
    - **message**: 更新成功消息

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
    config = ctx.life_on_line_config

    if "dailyPlanTimes" in payload:
        config.daily_plan_times = int(payload["dailyPlanTimes"])
    if "predefinedTeamIdx" in payload:
        config.predefined_team_idx = int(payload["predefinedTeamIdx"])

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
    record = ctx.life_on_line_record
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
    启动鼠标灵敏度检查器，自动检测和校准游戏中的鼠标灵敏度设置，确保操作精度。

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
    run_id = _run_via_onedragon_with_temp(["mouse_sensitivity_checker"])
    return RunIdResponse(runId=run_id)


# -------- Predefined Team Checker (预备编队识别) --------


@router.post("/predefined-team-checker/run", response_model=RunIdResponse, summary="运行预设队伍检查器")
async def run_predefined_team_checker():
    """
    启动预设队伍识别任务

    ## 功能描述
    启动预设队伍检查器，自动识别和验证游戏中的预设队伍配置，确保队伍设置正确。

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
    run_id = _run_via_onedragon_with_temp(["predefined_team_checker"])
    return RunIdResponse(runId=run_id)
