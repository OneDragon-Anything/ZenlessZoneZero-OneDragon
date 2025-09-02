from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

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


router = APIRouter(
    prefix="/api/v1/settings",
    tags=["settings"],
    dependencies=[Depends(get_api_key_dependency())],
)


@router.get("/game")
def get_game_settings() -> Dict[str, Any]:
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


@router.put("/game")
def update_game_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
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


@router.get("/keys")
def get_keys_settings() -> Dict[str, Any]:
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


@router.put("/keys")
def update_keys_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
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


@router.get("/agent-outfit")
def get_agent_outfit() -> Dict[str, Any]:
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


@router.put("/agent-outfit")
def update_agent_outfit(payload: Dict[str, Any]) -> Dict[str, Any]:
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


@router.get("/model")
def get_model_settings() -> Dict[str, Any]:
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


@router.put("/model")
def update_model_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
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


@router.get("/instance")
def get_instance_custom() -> Dict[str, Any]:
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


@router.put("/instance")
def update_instance_custom(payload: Dict[str, Any]) -> Dict[str, Any]:
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


@router.get("/notify")
def get_notify_settings() -> Dict[str, Any]:
    """
    对齐 GUI 逻辑：
    - apps: 来自 notify_config.app_list 及其动态属性
    - methods: 来源 PushCards.get_configs()，其结构为 { MethodName: [ {var_suffix, title, ...}, ... ] }
      我们返回 { method(lower): { var_suffix(lower): 当前值 } }
    - push: 基础 push 配置（标题 / 是否发送图片）
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


@router.put("/notify")
def update_notify_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
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
