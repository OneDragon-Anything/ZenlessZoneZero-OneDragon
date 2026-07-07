"""HTTP 应用运行服务端点。"""

import asyncio
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from zzz_od.backend.backend_context import BackendNotReadyError, ZzzBackendContext


def _err(msg: str, status: int = 503) -> JSONResponse:
    """构造统一错误 JSON 响应。"""
    return JSONResponse({"error": msg}, status_code=status)


async def handle_health(backend: ZzzBackendContext, _request: Request | None = None) -> Response:
    """处理 ``GET /health``：用于 GUI/脚本探测 server 是否为本项目后端。"""
    return JSONResponse({
        'ok': True,
        'server': 'zzz_od',
        'ready': bool(getattr(backend.ctx, 'ready_for_application', False)),
    })


async def handle_game_applications(backend: ZzzBackendContext, _request: Request | None = None) -> Response:
    """处理 ``GET /game/applications``：返回当前实例可运行应用。"""
    try:
        result = await asyncio.to_thread(backend.list_applications)
    except BackendNotReadyError as e:
        return _err(str(e))
    return JSONResponse(asdict(result))


async def handle_game_run_one_dragon(backend: ZzzBackendContext, request: Request | None = None) -> Response:
    """处理 ``POST /game/run/one-dragon?block=``：启动完整一条龙运行。"""
    block = False
    if request is not None:
        # HTTP 侧用 query 参数控制是否等待结束；默认与 MCP 一样非阻塞。
        block = request.query_params.get('block', 'false').lower() == 'true'
    try:
        ok, future = backend.run_one_dragon('http')
    except BackendNotReadyError as e:
        return _err(str(e))
    if not ok:
        st = backend.query_status()
        return JSONResponse({
            'started': False,
            'error': '已有运行在进行中',
            'source': st.source,
            'hint': '先 /game/status 查状态,或 /game/stop 停止',
        })
    if not block:
        # 非阻塞模式只返回启动摘要；运行详情统一由 /game/status 查询。
        st = backend.query_status()
        return JSONResponse({
            'started': True,
            'source': 'http',
            'app': st.app,
            'started_at': st.started_at,
            'hint': '用 /game/status 查进度与结果',
        })
    result = await asyncio.wrap_future(future)
    msg = '一条龙运行成功' if result and result.success else f"一条龙运行失败: {getattr(result, 'status', '无结果')}"
    return JSONResponse({'result': msg})


async def handle_game_run_standalone(backend: ZzzBackendContext, request: Request | None = None) -> Response:
    """处理 ``POST /game/run/standalone``：启动独立应用。"""
    block = False
    app_id = None
    if request is not None:
        block = request.query_params.get('block', 'false').lower() == 'true'
        app_id = request.query_params.get('app_id')
        if not app_id:
            try:
                # 兼容脚本用 JSON body 传 app_id；query/body 都没有时使用 GUI 当前选中项。
                body = await request.json()
                app_id = body.get('app_id') if isinstance(body, dict) else None
            except Exception:  # noqa: BLE001 空 body / 非 JSON 时使用 GUI 当前选中项
                app_id = None
    try:
        ok, future = backend.run_standalone_app('http', app_id=app_id)
    except BackendNotReadyError as e:
        return _err(str(e))
    if not ok:
        st = backend.query_status()
        return JSONResponse({
            'started': False,
            'error': '已有运行在进行中',
            'source': st.source,
            'hint': '先 /game/status 查状态,或 /game/stop 停止',
        })
    if not block:
        # 非阻塞模式只返回启动摘要；运行详情统一由 /game/status 查询。
        st = backend.query_status()
        return JSONResponse({
            'started': True,
            'source': 'http',
            'app': st.app,
            'started_at': st.started_at,
            'hint': '用 /game/status 查进度与结果',
        })
    result = await asyncio.wrap_future(future)
    msg = '独立应用运行成功' if result and result.success else f"独立应用运行失败: {getattr(result, 'status', '无结果')}"
    return JSONResponse({'result': msg})


def register_service_routes(mcp: FastMCP, backend: ZzzBackendContext) -> None:
    """注册应用运行服务端点。"""
    @mcp.custom_route("/health", methods=["GET"])
    async def _health(request: Request) -> Response:
        """GET /health 服务探测。"""
        return await handle_health(backend, request)

    @mcp.custom_route("/game/applications", methods=["GET"])
    async def _game_applications(request: Request) -> Response:
        """GET /game/applications 路由分发。"""
        return await handle_game_applications(backend, request)

    @mcp.custom_route("/game/run/one-dragon", methods=["POST"])
    async def _game_run_one_dragon(request: Request) -> Response:
        """POST /game/run/one-dragon 路由分发。"""
        return await handle_game_run_one_dragon(backend, request)

    @mcp.custom_route("/game/run/standalone", methods=["POST"])
    async def _game_run_standalone(request: Request) -> Response:
        """POST /game/run/standalone 路由分发。"""
        return await handle_game_run_standalone(backend, request)
