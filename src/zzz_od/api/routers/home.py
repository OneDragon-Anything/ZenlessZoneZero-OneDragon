from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict

import requests
from fastapi import APIRouter, Depends

from one_dragon.utils import app_utils, os_utils
from zzz_od.api.deps import get_ctx
from zzz_od.api.security import get_api_key_dependency


router = APIRouter(
    prefix="/api/v1/home",
    tags=["home"],
    dependencies=[Depends(get_api_key_dependency())],
)


@router.get("/version")
def get_version() -> Dict[str, str]:
    ctx = get_ctx()
    return {
        "launcherVersion": app_utils.get_launcher_version(),
        "codeVersion": ctx.git_service.get_current_version(),
    }


def _choose_banner(ctx) -> tuple[str, str, bool]:
    custom_banner_path = os.path.join(os_utils.get_path_under_work_dir('custom', 'assets', 'ui'), 'banner')
    version_poster_path = os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), 'version_poster.webp')
    remote_banner_path = os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), 'remote_banner.webp')
    index_banner_path = os.path.join(os_utils.get_path_under_work_dir('assets', 'ui'), 'index.png')

    if ctx.custom_config.custom_banner and os.path.exists(custom_banner_path):
        return "custom", custom_banner_path, True
    elif ctx.custom_config.version_poster and os.path.exists(version_poster_path):
        return "version_poster", version_poster_path, True
    elif ctx.custom_config.remote_banner and os.path.exists(remote_banner_path):
        return "remote", remote_banner_path, True
    else:
        return "default", index_banner_path, os.path.exists(index_banner_path)


@router.get("/banner")
def get_banner() -> Dict[str, Any]:
    ctx = get_ctx()
    mode, path, exists = _choose_banner(ctx)
    return {
        "mode": mode,
        "path": path,
        "exists": bool(exists),
        "settings": {
            "customBanner": ctx.custom_config.custom_banner,
            "remoteBanner": ctx.custom_config.remote_banner,
            "versionPoster": ctx.custom_config.version_poster,
        },
    }


@router.post("/banner")
def set_banner_settings(payload: Dict[str, Any]):
    ctx = get_ctx()
    if "customBanner" in payload:
        ctx.custom_config.custom_banner = bool(payload["customBanner"])
    if "remoteBanner" in payload:
        ctx.custom_config.remote_banner = bool(payload["remoteBanner"])
    if "versionPoster" in payload:
        ctx.custom_config.version_poster = bool(payload["versionPoster"])
    return {"ok": True}


@router.post("/banner:reload")
def reload_banner():
    ctx = get_ctx()

    assets_ui = os_utils.get_path_under_work_dir('assets', 'ui')
    os.makedirs(assets_ui, exist_ok=True)

    if ctx.custom_config.version_poster:
        url = "https://hyp-api.mihoyo.com/hyp/hyp-connect/api/getGames?launcher_id=jGHBHlcOq1&language=zh-cn"
        save_path = os.path.join(assets_ui, 'version_poster.webp')
        config_key = 'last_version_poster_fetch_time'

        def _extract(data):
            for game in data.get("data", {}).get("games", []):
                if game.get("biz") != "nap_cn":
                    continue
                display = game.get("display", {})
                background = display.get("background", {})
                if background:
                    return background.get("url")
            return None
    elif ctx.custom_config.remote_banner:
        url = "https://hyp-api.mihoyo.com/hyp/hyp-connect/api/getAllGameBasicInfo?launcher_id=jGHBHlcOq1&language=zh-cn"
        save_path = os.path.join(assets_ui, 'remote_banner.webp')
        config_key = 'last_remote_banner_fetch_time'

        def _extract(data):
            for game in data.get("data", {}).get("game_info_list", []):
                if game.get("game", {}).get("biz") != "nap_cn":
                    continue
                backgrounds = game.get("backgrounds", [])
                if backgrounds:
                    return backgrounds[0]["background"]["url"]
            return None
    else:
        return {"ok": True}

    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        img_url = _extract(data)
        if not img_url:
            return {"ok": False, "error": {"code": "NO_IMAGE", "message": "未获取到图片地址"}}
        img_resp = requests.get(img_url, timeout=8)
        if img_resp.status_code != 200:
            return {"ok": False, "error": {"code": "DOWNLOAD_FAIL", "message": "图片下载失败"}}
        tmp_path = save_path + '.tmp'
        with open(tmp_path, 'wb') as f:
            f.write(img_resp.content)
        if os.path.exists(save_path):
            os.remove(save_path)
        os.rename(tmp_path, save_path)
        setattr(ctx.custom_config, config_key, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": {"code": "EXCEPTION", "message": str(e)}}


@router.get("/notices")
def get_notices():
    ctx = get_ctx()
    return {"enabled": ctx.custom_config.notice_card}


@router.post("/notices")
def set_notices(payload: Dict[str, Any]):
    enabled = bool(payload.get("enabled", True))
    ctx = get_ctx()
    ctx.custom_config.notice_card = enabled
    return {"ok": True}


@router.get("/update/code")
def check_code_update():
    ctx = get_ctx()
    is_latest, msg = ctx.git_service.is_current_branch_latest()
    if msg == "与远程分支不一致":
        need_update = True
    elif msg != "获取远程代码失败":
        need_update = not is_latest
    else:
        need_update = False
    return {"needUpdate": bool(need_update), "message": msg}


@router.get("/update/model")
def check_model_update():
    ctx = get_ctx()
    need_update = ctx.model_config.using_old_model()
    return {"needUpdate": bool(need_update)}


