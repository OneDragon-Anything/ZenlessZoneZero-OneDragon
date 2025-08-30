from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from zzz_od.api.security import get_api_key_dependency
from zzz_od.config.model_config import (
    get_flash_classifier_opts,
    get_hollow_zero_event_opts,
    get_lost_void_det_opts,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.api.deps import get_ctx
from one_dragon.base.web.common_downloader import CommonDownloader, CommonDownloaderParam
from one_dragon.envs.env_config import (
    DEFAULT_GIT_PATH,
    DEFAULT_VENV_PYTHON_PATH,
)


router = APIRouter(
    prefix="/api/v1/resources",
    tags=["resources"],
    dependencies=[Depends(get_api_key_dependency())],
)


@router.get("/models")
def list_models() -> Dict[str, Any]:
    ctx: ZContext = get_ctx()
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


@router.post("/models/{name}:download")
def download_model(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    ctx: ZContext = get_ctx()
    # name in { flashClassifier, hollowZeroEvent, lostVoidDet }
    target = payload.get("target")  # 具体模型名，如 yolov8n-640-flash-20250622
    if not isinstance(target, str) or not target:
        return {"ok": False, "error": {"code": "INVALID_PARAM", "message": "target required"}}

    # 映射各模型的 CommonDownloaderParam
    opts_map = {
        "flashClassifier": get_flash_classifier_opts,
        "hollowZeroEvent": get_hollow_zero_event_opts,
        "lostVoidDet": get_lost_void_det_opts,
    }
    get_opts = opts_map.get(name)
    if get_opts is None:
        return {"ok": False, "error": {"code": "UNKNOWN_MODEL", "message": name}}

    selected_param: CommonDownloaderParam | None = None
    for opt in get_opts():
        if opt.label == target:
            selected_param = opt.value
            break
    if selected_param is None:
        return {"ok": False, "error": {"code": "MODEL_NOT_FOUND", "message": target}}

    downloader = CommonDownloader(selected_param)
    # 透传代理设置
    try:
        ok = downloader.download(
            ghproxy_url=ctx.env_config.gh_proxy_url if ctx.env_config.is_gh_proxy else None,
            proxy_url=ctx.env_config.personal_proxy if ctx.env_config.is_personal_proxy else None,
        )
        if not ok:
            return {"ok": False, "error": {"code": "DOWNLOAD_FAIL", "message": "download failed"}}
    except Exception as e:
        return {"ok": False, "error": {"code": "EXCEPTION", "message": str(e)}}

    # 应用配置
    if name == "flashClassifier":
        ctx.model_config.flash_classifier = target
        if "gpu" in payload:
            ctx.model_config.flash_classifier_gpu = bool(payload["gpu"])
    elif name == "hollowZeroEvent":
        ctx.model_config.hollow_zero_event = target
        if "gpu" in payload:
            ctx.model_config.hollow_zero_event_gpu = bool(payload["gpu"])
    elif name == "lostVoidDet":
        ctx.model_config.lost_void_det = target
        if "gpu" in payload:
            ctx.model_config.lost_void_det_gpu = bool(payload["gpu"])
    else:
        return {"ok": False, "error": {"code": "UNKNOWN_MODEL", "message": name}}

    return {"ok": True}


# --- Environment (git/python/uv/venv) ---


@router.get("/env")
def get_env_status() -> Dict[str, Any]:
    ctx: ZContext = get_ctx()
    ec = ctx.env_config
    ps = ctx.python_service
    gs = ctx.git_service

    return {
        "git": {
            "path": ec.git_path or DEFAULT_GIT_PATH,
            "version": gs.get_git_version(),
        },
        "uv": {
            "path": ec.uv_path,
            "version": ps.get_uv_version(),
        },
        "python": {
            "path": ec.python_path or DEFAULT_VENV_PYTHON_PATH,
            "version": ps.get_python_version(),
        },
        "venv": {
            "synced": ps.uv_check_sync_status(),
        },
        "sources": {
            "pip": ec.pip_source,
            "repositoryType": ec.repository_type,
            "gitMethod": ec.git_method,
            "branch": ec.git_branch,
            "ghProxyUrl": ec.gh_proxy_url,
            "isGhProxy": ec.is_gh_proxy,
            "isPersonalProxy": ec.is_personal_proxy,
            "personalProxy": ec.personal_proxy,
        },
        "options": {
            "forceUpdate": ec.force_update,
            "autoUpdate": ec.auto_update,
        },
    }


@router.post("/env/{name}:install")
def install_env(name: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    ctx: ZContext = get_ctx()
    ec = ctx.env_config
    ps = ctx.python_service
    gs = ctx.git_service
    payload = payload or {}

    if name == "git":
        ok, msg = gs.install_default_git(progress_callback=None)
        return {"ok": bool(ok), "message": msg}
    if name == "uv":
        ok, msg = ps.install_default_uv(progress_callback=None)
        return {"ok": bool(ok), "message": msg}
    if name == "python":
        ok = ps.install_standalone_python(progress_callback=None)
        return {"ok": bool(ok)}
    if name == "venv":
        ok = ps.uv_create_venv(progress_callback=None)
        if ok:
            ec.python_path = DEFAULT_VENV_PYTHON_PATH
        return {"ok": bool(ok)}
    if name == "sync":
        ok, msg = ps.uv_sync(progress_callback=None)
        return {"ok": bool(ok), "message": msg}

    return {"ok": False, "error": {"code": "UNKNOWN_ENV_TARGET", "message": name}}


