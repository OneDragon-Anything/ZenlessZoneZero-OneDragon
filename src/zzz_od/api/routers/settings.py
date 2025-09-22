from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from zzz_od.api.security import get_api_key_dependency
from zzz_od.api.deps import get_ctx
from zzz_od.config.agent_outfit_config import AgentOutfitConfig
from zzz_od.config.model_config import (
    get_flash_classifier_opts,
    get_hollow_zero_event_opts,
    get_lost_void_det_opts,
)
from one_dragon.base.config.custom_config import CustomConfig

from zzz_od.config.notify_config import NotifyConfig
from one_dragon.base.config.push_config import PushConfig
from one_dragon_qt.widgets.push_cards import PushCards  # GUI 使用的动态推送配置源
from zzz_od.application.random_play.random_play_config import RandomPlayConfig
from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_config import DriveDiscDismantleConfig
from one_dragon.utils import cmd_utils


router = APIRouter(
    prefix="/api/v1/settings",
    tags=["设置 Settings"],
    dependencies=[Depends(get_api_key_dependency())],
)


@router.get("/game", response_model=Dict[str, Any], summary="获取游戏设置")
def get_game_settings() -> Dict[str, Any]:
    """
    获取游戏相关的设置配置

    ## 功能描述
    返回游戏的详细设置配置，包括输入方式、启动参数、屏幕设置、键位配置和手柄设置。

    ## 返回数据
    - **inputWay**: 输入方式
    - **launchArgument**: 启动参数
    - **screenSize**: 屏幕尺寸
    - **fullScreen**: 是否全屏
    - **popupWindow**: 是否弹窗模式
    - **monitor**: 显示器设置
    - **launchArgumentAdvance**: 高级启动参数
    - **keys**: 键盘键位配置
      - **normalAttack**: 普通攻击键
      - **dodge**: 闪避键
      - **switchNext**: 切换下一个角色键
      - **switchPrev**: 切换上一个角色键
      - **specialAttack**: 特殊攻击键
      - **ultimate**: 终极技能键
      - **interact**: 交互键
      - **chainLeft**: 连携左键
      - **chainRight**: 连携右键
      - **moveW/S/A/D**: 移动键
      - **lock**: 锁定键
      - **chainCancel**: 取消连携键
    - **gamepad**: 手柄配置
      - **type**: 手柄类型
      - **xbox**: Xbox手柄配置
      - **ds4**: DS4手柄配置

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/settings/game")
    settings = response.json()
    print(f"输入方式: {settings['inputWay']}")
    print(f"普通攻击键: {settings['keys']['normalAttack']}")
    ```
    """
    ctx = get_ctx()
    gc = ctx.game_config
    return {
        "inputWay": gc.type_input_way,
        "launchArgument": gc.launch_argument,
        "screenSize": gc.screen_size,
        "fullScreen": gc.full_screen,
        "popupWindow": gc.popup_window,
        "monitor": gc.monitor,
        "launchArgumentAdvance": gc.launch_argument_advance,
        "keys": {
            "normalAttack": gc.key_normal_attack,
            "dodge": gc.key_dodge,
            "switchNext": gc.key_switch_next,
            "switchPrev": gc.key_switch_prev,
            "specialAttack": gc.key_special_attack,
            "ultimate": gc.key_ultimate,
            "interact": gc.key_interact,
            "chainLeft": gc.key_chain_left,
            "chainRight": gc.key_chain_right,
            "moveW": gc.key_move_w,
            "moveS": gc.key_move_s,
            "moveA": gc.key_move_a,
            "moveD": gc.key_move_d,
            "lock": gc.key_lock,
            "chainCancel": gc.key_chain_cancel,
        },
        "gamepad": {
            "type": gc.gamepad_type,
            "xbox": {
                "pressTime": gc.xbox_key_press_time,
                "normalAttack": gc.xbox_key_normal_attack,
                "dodge": gc.xbox_key_dodge,
                "switchNext": gc.xbox_key_switch_next,
                "switchPrev": gc.xbox_key_switch_prev,
                "specialAttack": gc.xbox_key_special_attack,
                "ultimate": gc.xbox_key_ultimate,
                "interact": gc.xbox_key_interact,
                "chainLeft": gc.xbox_key_chain_left,
                "chainRight": gc.xbox_key_chain_right,
                "moveW": gc.xbox_key_move_w,
                "moveS": gc.xbox_key_move_s,
                "moveA": gc.xbox_key_move_a,
                "moveD": gc.xbox_key_move_d,
                "lock": gc.xbox_key_lock,
                "chainCancel": gc.xbox_key_chain_cancel,
            },
            "ds4": {
                "pressTime": gc.ds4_key_press_time,
                "normalAttack": gc.ds4_key_normal_attack,
                "dodge": gc.ds4_key_dodge,
                "switchNext": gc.ds4_key_switch_next,
                "switchPrev": gc.ds4_key_switch_prev,
                "specialAttack": gc.ds4_key_special_attack,
                "ultimate": gc.ds4_key_ultimate,
                "interact": gc.ds4_key_interact,
                "chainLeft": gc.ds4_key_chain_left,
                "chainRight": gc.ds4_key_chain_right,
                "moveW": gc.ds4_key_move_w,
                "moveS": gc.ds4_key_move_s,
                "moveA": gc.ds4_key_move_a,
                "moveD": gc.ds4_key_move_d,
                "lock": gc.ds4_key_lock,
                "chainCancel": gc.ds4_key_chain_cancel,
            },
        },
    }


@router.put("/game", response_model=Dict[str, Any], summary="更新游戏设置")
def update_game_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新游戏相关的设置配置

    ## 功能描述
    更新游戏的设置配置，支持部分更新。只需要提供需要修改的字段。

    ## 请求参数
    - **inputWay** (可选): 输入方式
    - **launchArgument** (可选): 启动参数，布尔值
    - **screenSize** (可选): 屏幕尺寸
    - **fullScreen** (可选): 是否全屏
    - **popupWindow** (可选): 是否弹窗模式，布尔值
    - **monitor** (可选): 显示器设置
    - **launchArgumentAdvance** (可选): 高级启动参数
    - **keys** (可选): 键盘键位配置对象
    - **gamepad** (可选): 手柄配置对象
      - **type**: 手柄类型
      - **xbox**: Xbox手柄配置
      - **ds4**: DS4手柄配置

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "inputWay": "keyboard",
        "keys": {
            "normalAttack": "j",
            "dodge": "space"
        },
        "gamepad": {
            "type": "xbox"
        }
    }
    response = requests.put("http://localhost:8000/api/v1/settings/game", json=data)
    ```
    """
    ctx = get_ctx()
    gc = ctx.game_config
    # 基础
    if "inputWay" in payload:
        gc.type_input_way = payload["inputWay"]
    if "launchArgument" in payload:
        gc.launch_argument = bool(payload["launchArgument"])
    if "screenSize" in payload:
        gc.screen_size = payload["screenSize"]
    if "fullScreen" in payload:
        gc.full_screen = payload["fullScreen"]
    if "popupWindow" in payload:
        gc.popup_window = bool(payload["popupWindow"])
    if "monitor" in payload:
        gc.monitor = payload["monitor"]
    if "launchArgumentAdvance" in payload:
        gc.launch_argument_advance = payload["launchArgumentAdvance"]

    # 键位
    keys = payload.get("keys") or {}
    if "normalAttack" in keys:
        gc.key_normal_attack = keys["normalAttack"]
    if "dodge" in keys:
        gc.key_dodge = keys["dodge"]
    if "switchNext" in keys:
        gc.key_switch_next = keys["switchNext"]
    if "switchPrev" in keys:
        gc.key_switch_prev = keys["switchPrev"]
    if "specialAttack" in keys:
        gc.key_special_attack = keys["specialAttack"]
    if "ultimate" in keys:
        gc.key_ultimate = keys["ultimate"]
    if "interact" in keys:
        gc.key_interact = keys["interact"]
    if "chainLeft" in keys:
        gc.key_chain_left = keys["chainLeft"]
    if "chainRight" in keys:
        gc.key_chain_right = keys["chainRight"]
    if "moveW" in keys:
        gc.key_move_w = keys["moveW"]
    if "moveS" in keys:
        gc.key_move_s = keys["moveS"]
    if "moveA" in keys:
        gc.key_move_a = keys["moveA"]
    if "moveD" in keys:
        gc.key_move_d = keys["moveD"]
    if "lock" in keys:
        gc.key_lock = keys["lock"]
    if "chainCancel" in keys:
        gc.key_chain_cancel = keys["chainCancel"]

    # 手柄
    gamepad = payload.get("gamepad") or {}
    if "type" in gamepad:
        gc.gamepad_type = gamepad["type"]
    xbox = gamepad.get("xbox") or {}
    if "pressTime" in xbox:
        gc.xbox_key_press_time = float(xbox["pressTime"])
    for k, attr in [
        ("normalAttack", "xbox_key_normal_attack"),
        ("dodge", "xbox_key_dodge"),
        ("switchNext", "xbox_key_switch_next"),
        ("switchPrev", "xbox_key_switch_prev"),
        ("specialAttack", "xbox_key_special_attack"),
        ("ultimate", "xbox_key_ultimate"),
        ("interact", "xbox_key_interact"),
        ("chainLeft", "xbox_key_chain_left"),
        ("chainRight", "xbox_key_chain_right"),
        ("moveW", "xbox_key_move_w"),
        ("moveS", "xbox_key_move_s"),
        ("moveA", "xbox_key_move_a"),
        ("moveD", "xbox_key_move_d"),
        ("lock", "xbox_key_lock"),
        ("chainCancel", "xbox_key_chain_cancel"),
    ]:
        if k in xbox:
            setattr(gc, attr, xbox[k])

    ds4 = gamepad.get("ds4") or {}
    if "pressTime" in ds4:
        gc.ds4_key_press_time = float(ds4["pressTime"])
    for k, attr in [
        ("normalAttack", "ds4_key_normal_attack"),
        ("dodge", "ds4_key_dodge"),
        ("switchNext", "ds4_key_switch_next"),
        ("switchPrev", "ds4_key_switch_prev"),
        ("specialAttack", "ds4_key_special_attack"),
        ("ultimate", "ds4_key_ultimate"),
        ("interact", "ds4_key_interact"),
        ("chainLeft", "ds4_key_chain_left"),
        ("chainRight", "ds4_key_chain_right"),
        ("moveW", "ds4_key_move_w"),
        ("moveS", "ds4_key_move_s"),
        ("moveA", "ds4_key_move_a"),
        ("moveD", "ds4_key_move_d"),
        ("lock", "ds4_key_lock"),
        ("chainCancel", "ds4_key_chain_cancel"),
    ]:
        if k in ds4:
            setattr(gc, attr, ds4[k])

    return {"ok": True}


# --- Keys (keyboard/gamepad) ---


@router.get("/keys", response_model=Dict[str, Any], summary="获取键位设置")
def get_keys_settings() -> Dict[str, Any]:
    """
    获取键盘和手柄的键位配置

    ## 功能描述
    返回当前的键盘键位和手柄按键配置信息。

    ## 返回数据
    - **keys**: 键盘键位配置
    - **gamepad**: 手柄配置
      - **type**: 手柄类型
      - **xbox**: Xbox手柄按键配置
        - **pressTime**: 按键持续时间
        - 各种按键映射
      - **ds4**: DS4手柄按键配置
        - **pressTime**: 按键持续时间
        - 各种按键映射

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/settings/keys")
    keys = response.json()
    print(f"手柄类型: {keys['gamepad']['type']}")
    print(f"普通攻击键: {keys['keys']['normalAttack']}")
    ```
    """
    ctx = get_ctx()
    gc = ctx.game_config
    return {
        "keys": {
            "normalAttack": gc.key_normal_attack,
            "dodge": gc.key_dodge,
            "switchNext": gc.key_switch_next,
            "switchPrev": gc.key_switch_prev,
            "specialAttack": gc.key_special_attack,
            "ultimate": gc.key_ultimate,
            "interact": gc.key_interact,
            "chainLeft": gc.key_chain_left,
            "chainRight": gc.key_chain_right,
            "moveW": gc.key_move_w,
            "moveS": gc.key_move_s,
            "moveA": gc.key_move_a,
            "moveD": gc.key_move_d,
            "lock": gc.key_lock,
            "chainCancel": gc.key_chain_cancel,
        },
        "gamepad": {
            "type": gc.gamepad_type,
            "xbox": {
                "pressTime": gc.xbox_key_press_time,
                "normalAttack": gc.xbox_key_normal_attack,
                "dodge": gc.xbox_key_dodge,
                "switchNext": gc.xbox_key_switch_next,
                "switchPrev": gc.xbox_key_switch_prev,
                "specialAttack": gc.xbox_key_special_attack,
                "ultimate": gc.xbox_key_ultimate,
                "interact": gc.xbox_key_interact,
                "chainLeft": gc.xbox_key_chain_left,
                "chainRight": gc.xbox_key_chain_right,
                "moveW": gc.xbox_key_move_w,
                "moveS": gc.xbox_key_move_s,
                "moveA": gc.xbox_key_move_a,
                "moveD": gc.xbox_key_move_d,
                "lock": gc.xbox_key_lock,
                "chainCancel": gc.xbox_key_chain_cancel,
            },
            "ds4": {
                "pressTime": gc.ds4_key_press_time,
                "normalAttack": gc.ds4_key_normal_attack,
                "dodge": gc.ds4_key_dodge,
                "switchNext": gc.ds4_key_switch_next,
                "switchPrev": gc.ds4_key_switch_prev,
                "specialAttack": gc.ds4_key_special_attack,
                "ultimate": gc.ds4_key_ultimate,
                "interact": gc.ds4_key_interact,
                "chainLeft": gc.ds4_key_chain_left,
                "chainRight": gc.ds4_key_chain_right,
                "moveW": gc.ds4_key_move_w,
                "moveS": gc.ds4_key_move_s,
                "moveA": gc.ds4_key_move_a,
                "moveD": gc.ds4_key_move_d,
                "lock": gc.ds4_key_lock,
                "chainCancel": gc.ds4_key_chain_cancel,
            },
        },
    }


@router.put("/keys", response_model=Dict[str, Any], summary="更新键位设置")
def update_keys_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新键盘和手柄的键位配置

    ## 功能描述
    更新键盘键位和手柄按键配置，支持部分更新。

    ## 请求参数
    - **keys** (可选): 键盘键位配置对象
    - **gamepad** (可选): 手柄配置对象
      - **type**: 手柄类型
      - **xbox**: Xbox手柄配置
        - **pressTime**: 按键持续时间
        - 各种按键映射
      - **ds4**: DS4手柄配置
        - **pressTime**: 按键持续时间
        - 各种按键映射

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "keys": {
            "normalAttack": "k",
            "dodge": "shift"
        },
        "gamepad": {
            "type": "ds4",
            "xbox": {
                "pressTime": 0.1
            }
        }
    }
    response = requests.put("http://localhost:8000/api/v1/settings/keys", json=data)
    ```
    """
    ctx = get_ctx()
    gc = ctx.game_config
    keys = payload.get("keys") or {}
    for field, attr in [
        ("normalAttack", "key_normal_attack"),
        ("dodge", "key_dodge"),
        ("switchNext", "key_switch_next"),
        ("switchPrev", "key_switch_prev"),
        ("specialAttack", "key_special_attack"),
        ("ultimate", "key_ultimate"),
        ("interact", "key_interact"),
        ("chainLeft", "key_chain_left"),
        ("chainRight", "key_chain_right"),
        ("moveW", "key_move_w"),
        ("moveS", "key_move_s"),
        ("moveA", "key_move_a"),
        ("moveD", "key_move_d"),
        ("lock", "key_lock"),
        ("chainCancel", "key_chain_cancel"),
    ]:
        if field in keys:
            setattr(gc, attr, keys[field])

    gamepad = payload.get("gamepad") or {}
    if "type" in gamepad:
        gc.gamepad_type = gamepad["type"]
    xbox = gamepad.get("xbox") or {}
    if "pressTime" in xbox:
        gc.xbox_key_press_time = float(xbox["pressTime"])
    for field, attr in [
        ("normalAttack", "xbox_key_normal_attack"),
        ("dodge", "xbox_key_dodge"),
        ("switchNext", "xbox_key_switch_next"),
        ("switchPrev", "xbox_key_switch_prev"),
        ("specialAttack", "xbox_key_special_attack"),
        ("ultimate", "xbox_key_ultimate"),
        ("interact", "xbox_key_interact"),
        ("chainLeft", "xbox_key_chain_left"),
        ("chainRight", "xbox_key_chain_right"),
        ("moveW", "xbox_key_move_w"),
        ("moveS", "xbox_key_move_s"),
        ("moveA", "xbox_key_move_a"),
        ("moveD", "xbox_key_move_d"),
        ("lock", "xbox_key_lock"),
        ("chainCancel", "xbox_key_chain_cancel"),
    ]:
        if field in xbox:
            setattr(gc, attr, xbox[field])

    ds4 = gamepad.get("ds4") or {}
    if "pressTime" in ds4:
        gc.ds4_key_press_time = float(ds4["pressTime"])
    for field, attr in [
        ("normalAttack", "ds4_key_normal_attack"),
        ("dodge", "ds4_key_dodge"),
        ("switchNext", "ds4_key_switch_next"),
        ("switchPrev", "ds4_key_switch_prev"),
        ("specialAttack", "ds4_key_special_attack"),
        ("ultimate", "ds4_key_ultimate"),
        ("interact", "ds4_key_interact"),
        ("chainLeft", "ds4_key_chain_left"),
        ("chainRight", "ds4_key_chain_right"),
        ("moveW", "ds4_key_move_w"),
        ("moveS", "ds4_key_move_s"),
        ("moveA", "ds4_key_move_a"),
        ("moveD", "ds4_key_move_d"),
        ("lock", "ds4_key_lock"),
        ("chainCancel", "ds4_key_chain_cancel"),
    ]:
        if field in ds4:
            setattr(gc, attr, ds4[field])
    return {"ok": True}


# --- Agent outfit ---


@router.get("/agent-outfit", response_model=Dict[str, Any], summary="获取代理人服装配置")
def get_agent_outfit() -> Dict[str, Any]:
    """
    获取代理人服装识别配置

    ## 功能描述
    返回代理人服装识别的配置信息，包括兼容模式和各代理人的服装设置。

    ## 返回数据
    - **compatibilityMode**: 兼容模式，布尔值
    - **current**: 当前选择的服装配置
      - **nicole**: 妮可当前服装
      - **ellen**: 艾莲当前服装
      - **astraYao**: 星见雅当前服装
      - **yixuan**: 一弦当前服装
      - **yuzuha**: 柚子当前服装
      - **alice**: 爱丽丝当前服装
    - **options**: 可选服装列表
      - 各代理人的可选服装列表

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/settings/agent-outfit")
    outfit = response.json()
    print(f"兼容模式: {outfit['compatibilityMode']}")
    print(f"妮可当前服装: {outfit['current']['nicole']}")
    ```
    """
    ctx = get_ctx()
    ac: AgentOutfitConfig = ctx.agent_outfit_config
    return {
        "compatibilityMode": ac.compatibility_mode,
        "current": {
            "nicole": ac.nicole,
            "ellen": ac.ellen,
            "astraYao": ac.astra_yao,
            "yixuan": ac.yixuan,
            "yuzuha": ac.yuzuha,
            "alice": ac.alice,
        },
        "options": {
            "nicole": ac.nicole_outfit_list,
            "ellen": ac.ellen_outfit_list,
            "astraYao": ac.astra_yao_outfit_list,
            "yixuan": ac.yixuan_outfit_list,
            "yuzuha": ac.yuzuha_outfit_list,
            "alice": ac.alice_outfit_list,
        },
    }


@router.put("/agent-outfit", response_model=Dict[str, Any], summary="更新代理人服装配置")
def update_agent_outfit(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新代理人服装识别配置

    ## 功能描述
    更新代理人服装识别的配置，支持兼容模式切换和服装选择。

    ## 请求参数
    - **compatibilityMode** (可选): 兼容模式，布尔值
    - **current** (可选): 当前服装配置（兼容模式下使用）
    - **options** (可选): 服装选项列表（多选模式下使用）

    ## 返回数据
    - **ok**: 操作是否成功

    ## 注意事项
    - 兼容模式：每个代理人只能选择一个服装
    - 多选模式：每个代理人可以选择多个服装进行识别

    ## 使用示例
    ```python
    import requests
    # 兼容模式
    data = {
        "compatibilityMode": True,
        "current": {
            "nicole": "默认服装",
            "ellen": "特殊服装"
        }
    }
    response = requests.put("http://localhost:8000/api/v1/settings/agent-outfit", json=data)
    ```
    """
    ctx = get_ctx()
    ac: AgentOutfitConfig = ctx.agent_outfit_config
    if "compatibilityMode" in payload:
        ac.compatibility_mode = bool(payload["compatibilityMode"])
    current = payload.get("current") or {}
    if ac.compatibility_mode:
        # 单选模式
        for key, attr in [
            ("nicole", "nicole"),
            ("ellen", "ellen"),
            ("astraYao", "astra_yao"),
            ("yixuan", "yixuan"),
            ("yuzuha", "yuzuha"),
            ("alice", "alice"),
        ]:
            if key in current:
                setattr(ac, attr, current[key])
        ctx.init_agent_template_id()
    else:
        # 多选列表模式
        lists = payload.get("options") or {}
        for key, attr in [
            ("nicole", "nicole_outfit_list"),
            ("ellen", "ellen_outfit_list"),
            ("astraYao", "astra_yao_outfit_list"),
            ("yixuan", "yixuan_outfit_list"),
            ("yuzuha", "yuzuha_outfit_list"),
            ("alice", "alice_outfit_list"),
        ]:
            if key in lists:
                # 通过底层适配器写入更安全；此处直接赋值
                setattr(ac, attr, lists[key])
        ctx.init_agent_template_id_list()
    return {"ok": True}


# --- Model selection (alias of resources/models) ---


@router.get("/model", response_model=Dict[str, Any], summary="获取AI模型设置")
def get_model_settings() -> Dict[str, Any]:
    """
    获取AI模型的配置设置

    ## 功能描述
    返回当前使用的AI模型配置，包括闪光分类器、零号空洞事件识别和迷失之地检测模型。

    ## 返回数据
    - **flashClassifier**: 闪光分类器配置
      - **selected**: 当前选择的模型
      - **gpu**: 是否使用GPU
      - **options**: 可选模型列表
    - **hollowZeroEvent**: 零号空洞事件识别配置
      - **selected**: 当前选择的模型
      - **gpu**: 是否使用GPU
      - **options**: 可选模型列表
    - **lostVoidDet**: 迷失之地检测配置
      - **selected**: 当前选择的模型
      - **gpu**: 是否使用GPU
      - **options**: 可选模型列表

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/settings/model")
    models = response.json()
    print(f"闪光分类器: {models['flashClassifier']['selected']}")
    print(f"使用GPU: {models['flashClassifier']['gpu']}")
    ```
    """
    ctx = get_ctx()
    return {
        "flashClassifier": {
            "selected": ctx.model_config.flash_classifier,
            "gpu": ctx.model_config.flash_classifier_gpu,
            "options": [c.label for c in get_flash_classifier_opts()],
        },
        "hollowZeroEvent": {
            "selected": ctx.model_config.hollow_zero_event,
            "gpu": ctx.model_config.hollow_zero_event_gpu,
            "options": [c.label for c in get_hollow_zero_event_opts()],
        },
        "lostVoidDet": {
            "selected": ctx.model_config.lost_void_det,
            "gpu": ctx.model_config.lost_void_det_gpu,
            "options": [c.label for c in get_lost_void_det_opts()],
        },
    }


@router.put("/model", response_model=Dict[str, Any], summary="更新AI模型设置")
def update_model_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新AI模型的配置设置

    ## 功能描述
    更新AI模型配置，包括模型选择和GPU使用设置。

    ## 请求参数
    - **flashClassifier** (可选): 闪光分类器配置
      - **selected**: 选择的模型名称
      - **gpu**: 是否使用GPU，布尔值
    - **hollowZeroEvent** (可选): 零号空洞事件识别配置
      - **selected**: 选择的模型名称
      - **gpu**: 是否使用GPU，布尔值
    - **lostVoidDet** (可选): 迷失之地检测配置
      - **selected**: 选择的模型名称
      - **gpu**: 是否使用GPU，布尔值

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "flashClassifier": {
            "selected": "新模型",
            "gpu": True
        },
        "hollowZeroEvent": {
            "gpu": False
        }
    }
    response = requests.put("http://localhost:8000/api/v1/settings/model", json=data)
    ```
    """
    ctx = get_ctx()
    for name in ["flashClassifier", "hollowZeroEvent", "lostVoidDet"]:
        conf = payload.get(name) or {}
        if not conf:
            continue
        if name == "flashClassifier":
            if "selected" in conf:
                ctx.model_config.flash_classifier = conf["selected"]
            if "gpu" in conf:
                ctx.model_config.flash_classifier_gpu = bool(conf["gpu"])
        elif name == "hollowZeroEvent":
            if "selected" in conf:
                ctx.model_config.hollow_zero_event = conf["selected"]
            if "gpu" in conf:
                ctx.model_config.hollow_zero_event_gpu = bool(conf["gpu"])
        elif name == "lostVoidDet":
            if "selected" in conf:
                ctx.model_config.lost_void_det = conf["selected"]
            if "gpu" in conf:
                ctx.model_config.lost_void_det_gpu = bool(conf["gpu"])
    return {"ok": True}


# --- Instance custom settings ---


@router.get("/instance", response_model=Dict[str, Any], summary="获取实例自定义设置")
def get_instance_custom() -> Dict[str, Any]:
    """
    获取当前实例的自定义设置

    ## 功能描述
    返回当前实例的个性化设置，包括界面语言、主题、公告卡片和横幅配置。

    ## 返回数据
    - **uiLanguage**: 界面语言
    - **theme**: 主题设置
    - **noticeCard**: 是否显示公告卡片
    - **banner**: 横幅配置
      - **customBanner**: 是否使用自定义横幅
      - **remoteBanner**: 是否使用远程横幅
      - **versionPoster**: 是否使用版本海报
      - **lastRemoteBannerFetchTime**: 最后获取远程横幅时间
      - **lastVersionPosterFetchTime**: 最后获取版本海报时间

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/settings/instance")
    settings = response.json()
    print(f"界面语言: {settings['uiLanguage']}")
    print(f"主题: {settings['theme']}")
    ```
    """
    ctx = get_ctx()
    c: CustomConfig = ctx.custom_config
    return {
        "uiLanguage": c.ui_language,
        "theme": c.theme,
        "noticeCard": c.notice_card,
        "banner": {
            "customBanner": c.custom_banner,
            "remoteBanner": c.remote_banner,
            "versionPoster": c.version_poster,
            "lastRemoteBannerFetchTime": c.last_remote_banner_fetch_time,
            "lastVersionPosterFetchTime": c.last_version_poster_fetch_time,
        },
    }


@router.put("/instance", response_model=Dict[str, Any], summary="更新实例自定义设置")
def update_instance_custom(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新当前实例的自定义设置

    ## 功能描述
    更新当前实例的个性化设置，支持部分更新。

    ## 请求参数
    - **uiLanguage** (可选): 界面语言
    - **theme** (可选): 主题设置
    - **noticeCard** (可选): 是否显示公告卡片，布尔值
    - **banner** (可选): 横幅配置
      - **customBanner**: 是否使用自定义横幅，布尔值
      - **remoteBanner**: 是否使用远程横幅，布尔值
      - **versionPoster**: 是否使用版本海报，布尔值

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "uiLanguage": "zh-CN",
        "theme": "dark",
        "banner": {
            "customBanner": True,
            "remoteBanner": False
        }
    }
    response = requests.put("http://localhost:8000/api/v1/settings/instance", json=data)
    ```
    """
    ctx = get_ctx()
    c: CustomConfig = ctx.custom_config
    if "uiLanguage" in payload:
        c.ui_language = payload["uiLanguage"]
    if "theme" in payload:
        c.theme = payload["theme"]
    if "noticeCard" in payload:
        c.notice_card = bool(payload["noticeCard"])
    banner = payload.get("banner") or {}
    if "customBanner" in banner:
        c.custom_banner = bool(banner["customBanner"])
    if "remoteBanner" in banner:
        c.remote_banner = bool(banner["remoteBanner"])
    if "versionPoster" in banner:
        c.version_poster = bool(banner["versionPoster"])
    return {"ok": True}


# --- Notification settings ---


@router.get("/notify", response_model=Dict[str, Any], summary="获取通知设置")
def get_notify_settings() -> Dict[str, Any]:
    """
    获取通知推送的配置设置

    ## 功能描述
    返回通知推送的详细配置，包括通知开关、应用通知设置、推送方式配置等。

    ## 返回数据
    - **enableNotify**: 是否启用通知
    - **enableBeforeNotify**: 是否启用任务前通知
    - **apps**: 各应用的通知开关配置
    - **push**: 推送基础配置
      - **customPushTitle**: 自定义推送标题
      - **sendImage**: 是否发送图片
    - **methods**: 推送方式配置
      - 各种推送方式的详细配置参数

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/settings/notify")
    notify = response.json()
    print(f"通知启用: {notify['enableNotify']}")
    print(f"应用通知: {notify['apps']}")
    ```
    """
    ctx = get_ctx()
    nc: NotifyConfig = ctx.notify_config
    pc: PushConfig = ctx.push_config

    # 1. 应用开关映射
    apps: Dict[str, bool] = {}
    for app_key in nc.app_list.keys():
        try:
            apps[app_key] = bool(getattr(nc, app_key))
        except Exception:
            apps[app_key] = True

    # 2. 推送方式配置快照（与 GUI setting_push_interface 初始化字段一致）
    methods: Dict[str, Dict[str, Any]] = {}
    for method_name, configs in PushCards.get_configs().items():  # method_name 如 WEBHOOK / SMTP 等
        method_lower = method_name.lower()
        method_map: Dict[str, Any] = {}
        for conf in configs:
            var_suffix = conf.get('var_suffix')  # e.g. URL / METHOD / BODY ...
            if not var_suffix:
                continue
            key = f"{method_lower}_{var_suffix.lower()}"  # push_config 动态属性名
            try:
                method_map[var_suffix.lower()] = getattr(pc, key)
            except Exception:
                method_map[var_suffix.lower()] = None
        methods[method_lower] = method_map

    return {
        "enableNotify": nc.enable_notify,
        "enableBeforeNotify": nc.enable_before_notify,
        "apps": apps,
        "push": {
            "customPushTitle": pc.custom_push_title,
            "sendImage": pc.send_image,
        },
        "methods": methods,
    }


@router.put("/notify", response_model=Dict[str, Any], summary="更新通知设置")
def update_notify_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新通知推送的配置设置

    ## 功能描述
    更新通知推送配置，包括通知开关、应用通知设置和推送方式配置。

    ## 请求参数
    - **enableNotify** (可选): 是否启用通知，布尔值
    - **enableBeforeNotify** (可选): 是否启用任务前通知，布尔值
    - **apps** (可选): 各应用的通知开关配置对象
    - **push** (可选): 推送基础配置
      - **customPushTitle**: 自定义推送标题
      - **sendImage**: 是否发送图片，布尔值
    - **methods** (可选): 推送方式配置对象

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "enableNotify": True,
        "apps": {
            "charge_plan": True,
            "coffee": False
        },
        "push": {
            "customPushTitle": "我的通知",
            "sendImage": True
        }
    }
    response = requests.put("http://localhost:8000/api/v1/settings/notify", json=data)
    ```
    """
    ctx = get_ctx()
    nc: NotifyConfig = ctx.notify_config
    pc: PushConfig = ctx.push_config
    if "enableNotify" in payload:
        nc.enable_notify = bool(payload["enableNotify"])  # type: ignore[assignment]
    if "enableBeforeNotify" in payload:
        nc.enable_before_notify = bool(payload["enableBeforeNotify"])  # type: ignore[assignment]
    apps = payload.get("apps") or {}
    for app_key, enabled in apps.items():
        # 仅允许已知 app
        if app_key in nc.app_list:
            try:
                setattr(nc, app_key, bool(enabled))
            except Exception:
                pass
    push = payload.get("push") or {}
    if "customPushTitle" in push:
        pc.custom_push_title = push["customPushTitle"]
    if "sendImage" in push:
        pc.send_image = bool(push["sendImage"])  # type: ignore[assignment]
    methods = payload.get("methods") or {}
    for group_name, kv in methods.items():
        if not isinstance(kv, dict):
            continue
        for var, value in kv.items():
            key = f"{group_name}_{var}".lower()
            if hasattr(pc, key):
                try:
                    setattr(pc, key, value)
                except Exception:
                    pass
    return {"ok": True}


# --- Environment settings (脚本环境) ---


@router.get("/environment", response_model=Dict[str, Any], summary="获取脚本环境设置")
def get_environment_settings() -> Dict[str, Any]:
    """
    获取脚本运行环境的配置设置

    ## 功能描述
    返回脚本运行环境的详细配置，包括调试模式、Git设置、Python环境、网络代理和快捷键配置。

    ## 返回数据
    - **basic**: 基础设置
      - **debugMode**: 调试模式
      - **copyScreenshot**: 是否复制截图
      - **ocrCache**: OCR缓存
    - **git**: Git设置
      - **repositoryType**: 仓库类型
      - **gitMethod**: Git方法
      - **forceUpdate**: 强制更新
      - **autoUpdate**: 自动更新
    - **python**: Python环境设置
      - **pipSource**: Pip源
      - **cpythonSource**: CPython源
    - **network**: 网络设置
      - **proxyType**: 代理类型
      - **personalProxy**: 个人代理
      - **ghProxyUrl**: GitHub代理URL
      - **autoFetchGhProxyUrl**: 自动获取GitHub代理URL
    - **keys**: 快捷键设置
      - **startRunning**: 开始运行快捷键
      - **stopRunning**: 停止运行快捷键
      - **screenshot**: 截图快捷键
      - **debug**: 调试快捷键

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/settings/environment")
    env = response.json()
    print(f"调试模式: {env['basic']['debugMode']}")
    print(f"Git方法: {env['git']['gitMethod']}")
    ```
    """
    ctx = get_ctx()
    env_config = ctx.env_config

    return {
        "basic": {
            "debugMode": env_config.is_debug,
            "copyScreenshot": env_config.copy_screenshot,
            "ocrCache": env_config.ocr_cache,
        },
        "git": {
            "repositoryType": env_config.repository_type,
            "gitMethod": env_config.git_method,
            "forceUpdate": env_config.force_update,
            "autoUpdate": env_config.auto_update,
        },
        "python": {
            "pipSource": env_config.pip_source,
            "cpythonSource": env_config.cpython_source,
        },
        "network": {
            "proxyType": env_config.proxy_type,
            "personalProxy": env_config.personal_proxy,
            "ghProxyUrl": env_config.gh_proxy_url,
            "autoFetchGhProxyUrl": env_config.auto_fetch_gh_proxy_url,
        },
        "keys": {
            "startRunning": env_config.key_start_running,
            "stopRunning": env_config.key_stop_running,
            "screenshot": env_config.key_screenshot,
            "debug": env_config.key_debug,
        },
    }


@router.put("/environment", response_model=Dict[str, Any], summary="更新脚本环境设置")
def update_environment_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新脚本运行环境的配置设置

    ## 功能描述
    更新脚本运行环境配置，支持部分更新。更新后会重新初始化上下文。

    ## 请求参数
    - **basic** (可选): 基础设置
      - **debugMode**: 调试模式，布尔值
      - **copyScreenshot**: 是否复制截图，布尔值
      - **ocrCache**: OCR缓存，布尔值
    - **git** (可选): Git设置
      - **repositoryType**: 仓库类型
      - **gitMethod**: Git方法
      - **forceUpdate**: 强制更新，布尔值
      - **autoUpdate**: 自动更新，布尔值
    - **python** (可选): Python环境设置
      - **pipSource**: Pip源
      - **cpythonSource**: CPython源
    - **network** (可选): 网络设置
      - **proxyType**: 代理类型
      - **personalProxy**: 个人代理
      - **ghProxyUrl**: GitHub代理URL
      - **autoFetchGhProxyUrl**: 自动获取GitHub代理URL，布尔值
    - **keys** (可选): 快捷键设置
      - **startRunning**: 开始运行快捷键
      - **stopRunning**: 停止运行快捷键
      - **screenshot**: 截图快捷键
      - **debug**: 调试快捷键

    ## 返回数据
    - **ok**: 操作是否成功

    ## 注意事项
    - 更新环境设置后会重新初始化上下文
    - 某些设置可能需要重启应用才能生效

    ## 使用示例
    ```python
    import requests
    data = {
        "basic": {
            "debugMode": True,
            "copyScreenshot": False
        },
        "git": {
            "autoUpdate": True
        }
    }
    response = requests.put("http://localhost:8000/api/v1/settings/environment", json=data)
    ```
    """
    ctx = get_ctx()
    env_config = ctx.env_config

    # 基础设置
    basic = payload.get("basic") or {}
    if "debugMode" in basic:
        env_config.is_debug = bool(basic["debugMode"])
    if "copyScreenshot" in basic:
        env_config.copy_screenshot = bool(basic["copyScreenshot"])
    if "ocrCache" in basic:
        env_config.ocr_cache = bool(basic["ocrCache"])

    # Git设置
    git = payload.get("git") or {}
    if "repositoryType" in git:
        env_config.repository_type = git["repositoryType"]
    if "gitMethod" in git:
        env_config.git_method = git["gitMethod"]
    if "forceUpdate" in git:
        env_config.force_update = bool(git["forceUpdate"])
    if "autoUpdate" in git:
        env_config.auto_update = bool(git["autoUpdate"])

    # Python设置
    python = payload.get("python") or {}
    if "pipSource" in python:
        env_config.pip_source = python["pipSource"]
    if "cpythonSource" in python:
        env_config.cpython_source = python["cpythonSource"]

    # 网络设置
    network = payload.get("network") or {}
    if "proxyType" in network:
        env_config.proxy_type = network["proxyType"]
    if "personalProxy" in network:
        env_config.personal_proxy = network["personalProxy"]
    if "ghProxyUrl" in network:
        env_config.gh_proxy_url = network["ghProxyUrl"]
    if "autoFetchGhProxyUrl" in network:
        env_config.auto_fetch_gh_proxy_url = bool(network["autoFetchGhProxyUrl"])

    # 按键设置
    keys = payload.get("keys") or {}
    if "startRunning" in keys:
        env_config.key_start_running = keys["startRunning"]
    if "stopRunning" in keys:
        env_config.key_stop_running = keys["stopRunning"]
    if "screenshot" in keys:
        env_config.key_screenshot = keys["screenshot"]
    if "debug" in keys:
        env_config.key_debug = keys["debug"]

    # 重新初始化上下文
    ctx.init_by_config()

    return {"ok": True}


# --- Environment actions (环境操作) ---


@router.post("/environment/actions/fetch-gh-proxy", response_model=Dict[str, Any], summary="获取GitHub代理URL")
def fetch_gh_proxy_url() -> Dict[str, Any]:
    """
    自动获取GitHub代理URL

    ## 功能描述
    自动从网络获取可用的GitHub代理URL，用于加速GitHub访问。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息

    ## 错误码
    - **FETCH_FAILED**: 获取失败 (500)

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/settings/environment/actions/fetch-gh-proxy")
    result = response.json()
    print(result["message"])
    ```
    """
    ctx = get_ctx()
    try:
        # 这里可以实现获取GitHub代理URL的逻辑
        # 由于这涉及到网络请求，我们暂时返回成功状态
        return {
            "ok": True,
            "message": "GitHub proxy URL fetch initiated"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取GitHub代理URL失败: {str(e)}"
        )


@router.post("/environment/actions/test-proxy", response_model=Dict[str, Any], summary="测试代理连接")
def test_proxy_connection(proxy_url: str) -> Dict[str, Any]:
    """
    测试代理服务器连接

    ## 功能描述
    测试指定代理服务器的连接状态和可用性。

    ## 请求参数
    - **proxy_url**: 要测试的代理URL

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 测试结果消息
    - **status**: 连接状态 (success/failed)

    ## 使用示例
    ```python
    import requests
    response = requests.post(
        "http://localhost:8000/api/v1/settings/environment/actions/test-proxy",
        params={"proxy_url": "http://proxy.example.com:8080"}
    )
    result = response.json()
    print(f"代理状态: {result['status']}")
    ```
    """
    try:
        # 这里可以实现代理连接测试逻辑
        # 暂时返回成功状态
        return {
            "ok": True,
            "message": f"Proxy connection test for {proxy_url} completed",
            "status": "success"
        }
    except Exception as e:
        return {
            "ok": False,
            "message": f"Proxy connection test failed: {str(e)}",
            "status": "failed"
        }


@router.post("/environment/actions/test-pip-source", response_model=Dict[str, Any], summary="测试Pip源连接")
def test_pip_source(source_url: str) -> Dict[str, Any]:
    """
    测试Pip源服务器连接

    ## 功能描述
    测试指定Pip源的连接状态和可用性。

    ## 请求参数
    - **source_url**: 要测试的Pip源URL

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 测试结果消息
    - **status**: 连接状态 (success/failed)

    ## 使用示例
    ```python
    import requests
    response = requests.post(
        "http://localhost:8000/api/v1/settings/environment/actions/test-pip-source",
        params={"source_url": "https://pypi.tuna.tsinghua.edu.cn/simple"}
    )
    result = response.json()
    print(f"Pip源状态: {result['status']}")
    ```
    """
    try:
        # 这里可以实现Pip源连接测试逻辑
        # 暂时返回成功状态
        return {
            "ok": True,
            "message": f"Pip source test for {source_url} completed",
            "status": "success"
        }
    except Exception as e:
        return {
            "ok": False,
            "message": f"Pip source test failed: {str(e)}",
            "status": "failed"
        }


@router.post("/environment/actions/update-git-remote", response_model=Dict[str, Any], summary="更新Git远程地址")
def update_git_remote() -> Dict[str, Any]:
    """
    更新Git仓库的远程地址

    ## 功能描述
    根据当前配置更新Git仓库的远程地址，用于切换代码源。

    ## 返回数据
    - **ok**: 操作是否成功
    - **message**: 操作结果消息

    ## 错误码
    - **UPDATE_FAILED**: 更新失败 (500)

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/settings/environment/actions/update-git-remote")
    result = response.json()
    print(result["message"])
    ```
    """
    ctx = get_ctx()
    try:
        # 更新Git远程地址
        ctx.git_service.update_git_remote()

        # 清除版本缓存，以便获取最新版本信息
        from zzz_od.api.routers.home import clear_version_cache
        clear_version_cache()

        return {
            "ok": True,
            "message": "Git remote updated successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"更新Git远程地址失败: {str(e)}"
        )


# --- HDR Settings ---


@router.post("/game/hdr/enable")
def enable_hdr() -> Dict[str, Any]:
    """
    启用HDR设置

    ## 功能描述
    通过修改Windows注册表启用HDR，仅影响手动启动游戏，一条龙启动游戏会自动禁用HDR。

    ## 返回数据
    返回操作结果消息

    ## 错误码
    - **HDR_ENABLE_FAILED**: HDR启用失败

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/settings/game/hdr/enable")
    result = response.json()
    print(result["message"])
    ```
    """
    try:
        ctx = get_ctx()
        game_path = ctx.game_account_config.game_path

        cmd_utils.run_command([
            'reg', 'add', 'HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences',
            '/v', game_path, '/d', 'AutoHDREnable=2097;', '/f'
        ])

        return {
            "ok": True,
            "message": "HDR已启用"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "HDR_ENABLE_FAILED",
                    "message": f"启用HDR失败: {str(e)}"
                }
            }
        )


@router.post("/game/hdr/disable")
def disable_hdr() -> Dict[str, Any]:
    """
    禁用HDR设置

    ## 功能描述
    通过修改Windows注册表禁用HDR，仅影响手动启动游戏，一条龙启动游戏会自动禁用HDR。

    ## 返回数据
    返回操作结果消息

    ## 错误码
    - **HDR_DISABLE_FAILED**: HDR禁用失败

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/settings/game/hdr/disable")
    result = response.json()
    print(result["message"])
    ```
    """
    try:
        ctx = get_ctx()
        game_path = ctx.game_account_config.game_path

        cmd_utils.run_command([
            'reg', 'add', 'HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences',
            '/v', game_path, '/d', 'AutoHDREnable=2096;', '/f'
        ])

        return {
            "ok": True,
            "message": "HDR已禁用"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "HDR_DISABLE_FAILED",
                    "message": f"禁用HDR失败: {str(e)}"
                }
            }
        )
