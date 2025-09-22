from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, Depends

from one_dragon.utils import app_utils, os_utils
from zzz_od.api.deps import get_ctx
from zzz_od.api.security import get_api_key_dependency


router = APIRouter(
    prefix="/api/v1/home",
    tags=["首页 Home"],
    dependencies=[Depends(get_api_key_dependency())],
)

# 版本信息缓存
_version_cache: Optional[Dict[str, str]] = None
_version_cache_time: float = 0
_version_cache_ttl: float = 300  # 缓存5分钟


def clear_version_cache():
    """清除版本缓存，用于代码更新后立即获取新版本"""
    global _version_cache, _version_cache_time
    _version_cache = None
    _version_cache_time = 0


@router.get("/version", response_model=Dict[str, str], summary="获取版本信息")
def get_version() -> Dict[str, str]:
    """
    获取应用程序版本信息

    ## 功能描述
    返回启动器版本和代码版本信息，用于版本检查和显示。
    版本信息会缓存5分钟，减少git命令调用频率。

    ## 返回数据
    - **launcherVersion**: 启动器版本号
    - **codeVersion**: 代码版本号

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/home/version")
    version_info = response.json()
    print(f"启动器版本: {version_info['launcherVersion']}")
    print(f"代码版本: {version_info['codeVersion']}")
    ```
    """
    global _version_cache, _version_cache_time

    current_time = time.time()

    # 检查缓存是否有效
    if _version_cache is None or (current_time - _version_cache_time) > _version_cache_ttl:
        ctx = get_ctx()
        _version_cache = {
            "launcherVersion": app_utils.get_launcher_version(),
            "codeVersion": ctx.git_service.get_current_version(),
        }
        _version_cache_time = current_time

    return _version_cache


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


@router.get("/banner", response_model=Dict[str, Any], summary="获取横幅配置")
def get_banner() -> Dict[str, Any]:
    """
    获取首页横幅的配置和状态

    ## 功能描述
    返回当前横幅的显示模式、路径和相关设置信息。

    ## 返回数据
    - **mode**: 横幅模式 (custom/version_poster/remote/default)
    - **path**: 横幅文件路径
    - **exists**: 文件是否存在
    - **settings**: 横幅设置
      - **customBanner**: 是否启用自定义横幅
      - **remoteBanner**: 是否启用远程横幅
      - **versionPoster**: 是否启用版本海报

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/home/banner")
    banner_info = response.json()
    print(f"横幅模式: {banner_info['mode']}")
    ```
    """
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


@router.post("/banner", summary="设置横幅配置")
def set_banner_settings(payload: Dict[str, Any]):
    """
    更新首页横幅的显示设置

    ## 功能描述
    更新横幅的显示配置，包括自定义横幅、远程横幅和版本海报的开关。

    ## 请求参数
    - **customBanner** (可选): 是否启用自定义横幅，布尔值
    - **remoteBanner** (可选): 是否启用远程横幅，布尔值
    - **versionPoster** (可选): 是否启用版本海报，布尔值

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {
        "customBanner": True,
        "remoteBanner": False
    }
    response = requests.post("http://localhost:8000/api/v1/home/banner", json=data)
    print(response.json()["ok"])
    ```
    """
    ctx = get_ctx()
    if "customBanner" in payload:
        ctx.custom_config.custom_banner = bool(payload["customBanner"])
    if "remoteBanner" in payload:
        ctx.custom_config.remote_banner = bool(payload["remoteBanner"])
    if "versionPoster" in payload:
        ctx.custom_config.version_poster = bool(payload["versionPoster"])
    return {"ok": True}


@router.post("/banner:reload", summary="重新加载横幅")
def reload_banner():
    """
    重新下载和加载横幅图片

    ## 功能描述
    根据当前设置重新从远程服务器下载横幅图片，包括版本海报和远程横幅。

    ## 返回数据
    - **ok**: 操作是否成功
    - **error** (可选): 错误信息
      - **code**: 错误代码
      - **message**: 错误消息

    ## 错误码
    - **NO_IMAGE**: 未获取到图片地址
    - **DOWNLOAD_FAIL**: 图片下载失败
    - **EXCEPTION**: 其他异常

    ## 使用示例
    ```python
    import requests
    response = requests.post("http://localhost:8000/api/v1/home/banner:reload")
    result = response.json()
    if result["ok"]:
        print("横幅重新加载成功")
    else:
        print(f"加载失败: {result['error']['message']}")
    ```
    """
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


@router.get("/notices", summary="获取公告设置")
def get_notices():
    """
    获取公告卡片的显示设置

    ## 功能描述
    返回首页公告卡片是否启用的设置状态。

    ## 返回数据
    - **enabled**: 是否启用公告卡片显示

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/home/notices")
    notices_info = response.json()
    print(f"公告启用状态: {notices_info['enabled']}")
    ```
    """
    ctx = get_ctx()
    return {"enabled": ctx.custom_config.notice_card}


@router.post("/notices", summary="设置公告显示")
def set_notices(payload: Dict[str, Any]):
    """
    设置公告卡片的显示状态

    ## 功能描述
    更新首页公告卡片的显示开关设置。

    ## 请求参数
    - **enabled**: 是否启用公告卡片显示，布尔值

    ## 返回数据
    - **ok**: 操作是否成功

    ## 使用示例
    ```python
    import requests
    data = {"enabled": True}
    response = requests.post("http://localhost:8000/api/v1/home/notices", json=data)
    print(response.json()["ok"])
    ```
    """
    enabled = bool(payload.get("enabled", True))
    ctx = get_ctx()
    ctx.custom_config.notice_card = enabled
    return {"ok": True}


@router.get("/update/code", summary="检查代码更新")
def check_code_update():
    """
    检查代码是否有可用更新

    ## 功能描述
    检查当前代码版本与远程仓库的最新版本，判断是否需要更新。

    ## 返回数据
    - **needUpdate**: 是否需要更新，布尔值
    - **message**: 检查结果消息

    ## 可能的消息
    - "与远程分支不一致": 需要更新
    - "获取远程代码失败": 网络或其他错误
    - 其他状态消息

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/home/update/code")
    update_info = response.json()
    if update_info["needUpdate"]:
        print(f"需要更新: {update_info['message']}")
    else:
        print("代码已是最新版本")
    ```
    """
    ctx = get_ctx()
    is_latest, msg = ctx.git_service.is_current_branch_latest()
    if msg == "与远程分支不一致":
        need_update = True
    elif msg != "获取远程代码失败":
        need_update = not is_latest
    else:
        need_update = False
    return {"needUpdate": bool(need_update), "message": msg}


@router.get("/update/model", summary="检查模型更新")
def check_model_update():
    """
    检查AI模型是否有可用更新

    ## 功能描述
    检查当前使用的AI模型是否为旧版本，判断是否需要更新到最新模型。

    ## 返回数据
    - **needUpdate**: 是否需要更新模型，布尔值

    ## 使用示例
    ```python
    import requests
    response = requests.get("http://localhost:8000/api/v1/home/update/model")
    model_info = response.json()
    if model_info["needUpdate"]:
        print("需要更新AI模型")
    else:
        print("AI模型已是最新版本")
    ```
    """
    ctx = get_ctx()
    need_update = ctx.model_config.using_old_model()
    return {"needUpdate": bool(need_update)}


