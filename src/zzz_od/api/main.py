from __future__ import annotations

import sys
import ctypes

# Set DPI awareness for the process on Windows
if sys.platform == 'win32':
    try:
        # For Windows 8.1 and higher. 2 corresponds to PER_MONITOR_AWARE_V2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            # For Windows Vista and higher
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass  # Not supported



import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from zzz_od.api.deps import get_ctx
from zzz_od.api import log_stream
from zzz_od.api.ws import router as ws_router
from zzz_od.api.routers import home, accounts, onedragon
from zzz_od.api.routers import runs as runs_router
from zzz_od.api.routers import resources as resources_router
from zzz_od.api.routers import settings as settings_router
from zzz_od.api.routers import world_patrol as world_patrol_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure ctx initialized
    try:
        get_ctx()
        # 启动日志流 (INFO 及以上)
        log_stream.start_log_stream()
        yield
    finally:
        # Shutdown: best-effort stop
        try:
            get_ctx().stop_running()
        except Exception:
            pass
        try:
            # 优雅停止日志流
            import asyncio
            # lifespan 退出仍在事件循环内, 可直接 await
            await log_stream.stop_log_stream()
        except Exception:
            pass


app = FastAPI(title="OneDragon ZZZ API", version="v1", lifespan=lifespan)

# CORS - allow local tools by default (configurable later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:*",
        "http://127.0.0.1",
        "http://127.0.0.1:*",
        "tauri://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers: uniform error envelope
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.exception("Validation error: %s", exc)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数校验失败",
                "details": {"errors": exc.errors()},
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logging.exception("HTTP error: %s", exc)
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    details = None if isinstance(exc.detail, str) else exc.detail
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": message, "details": details}},
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/version")
def version_alias():
    ctx = get_ctx()
    from one_dragon.utils import app_utils

    return {
        "version": app_utils.get_launcher_version(),
        "gitRevision": ctx.git_service.get_current_version(),
    }


# Routers
app.include_router(home.router)
app.include_router(accounts.router)
app.include_router(onedragon.router)
app.include_router(runs_router.router)
app.include_router(resources_router.router)
app.include_router(settings_router.router)
app.include_router(world_patrol_router.router)
app.include_router(ws_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
