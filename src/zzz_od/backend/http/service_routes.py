"""HTTP 应用运行服务端点。"""

import asyncio
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from zzz_od.backend import operation_registry
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


async def handle_game_predefined_teams(backend: ZzzBackendContext, _request: Request | None = None) -> Response:
    """处理 ``GET /game/predefined-teams``：返回当前实例的预备编队。"""
    try:
        result = await asyncio.to_thread(backend.list_predefined_teams)
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


async def handle_game_operations(backend: ZzzBackendContext, _request: Request | None = None) -> Response:
    """处理 ``GET /game/operations``:列出可运行的自定义 operation(纯反射,无副作用)。

    业务失败一律 ``200 + body``(``{error}``),不引入 4xx/5xx(除 backend 未就绪)。
    """
    try:
        result = await asyncio.to_thread(operation_registry.scan_operations, backend.ctx)
    except BackendNotReadyError as e:
        return _err(str(e))
    except Exception as e:  # noqa: BLE001 扫描异常兜底
        return JSONResponse({'error': str(e)})
    return JSONResponse(asdict(result))


async def handle_game_operations_describe(
    backend: ZzzBackendContext, request: Request | None = None,
) -> Response:
    """处理 ``GET /game/operations/describe?op_id=``:描述单个 operation 参数 schema。

    op_id 走 query 参数;业务失败(缺 op_id / 解析失败)一律 ``200 + {error}``。
    """
    op_id = None
    if request is not None:
        op_id = request.query_params.get('op_id')
    if not op_id:
        return JSONResponse({'error': '缺少 op_id query 参数'})
    try:
        info = await asyncio.to_thread(operation_registry.describe_operation, backend.ctx, op_id)
    except BackendNotReadyError as e:
        return _err(str(e))
    except Exception as e:  # noqa: BLE001 解析异常兜底
        return JSONResponse({'error': str(e)})
    return JSONResponse(info)


async def handle_game_run_operation(
    backend: ZzzBackendContext, request: Request | None = None,
) -> Response:
    """处理 ``POST /game/run/operation?op_id=&block=``:运行自定义 operation(args 走 JSON body)。

    op_id、block 走 query;args 走 JSON body(整体 body 即 args 字典,空 body 时 args={})。
    resolve_op_class + validate_args 先校验,通过后 op_factory 闭包 bake args 提交单跑道。
    业务失败(非 Operation / 缺参 / 复杂数据类 / 并发拒绝)一律 ``200 + {started: False, error}``。
    """
    op_id: str | None = None
    block = False
    args: dict = {}
    if request is not None:
        op_id = request.query_params.get('op_id')
        block = request.query_params.get('block', 'false').lower() == 'true'
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 空 body / 非 JSON 时 args={}
            body = None
        if isinstance(body, dict):
            args = body
    if not op_id:
        return JSONResponse({'started': False, 'error': '缺少 op_id query 参数'})
    try:
        cls = operation_registry.resolve_op_class(op_id)
        err = operation_registry.validate_args(cls, args or {})
        if err:
            return JSONResponse({'started': False, 'error': err})
        # 闭包 bake args(与 MCP 侧一致:槽只认 op_factory(ctx) → Operation)
        def op_factory(ctx):  # noqa: ANN202 闭包签名固定 Callable[[ZContext], Operation]
            return cls(ctx, **(args or {}))
        ok, future = backend.run_slot._start('http', op_factory=op_factory, display_name=op_id)
    except Exception as e:  # noqa: BLE001 resolve/validate/_start 异常兜底
        return JSONResponse({'started': False, 'error': str(e)})
    if not ok:
        st = backend.query_status()
        return JSONResponse({
            'started': False,
            'error': '已有运行在进行中',
            'source': st.source,
            'hint': '先 /game/status 查状态,或 /game/stop 停止',
        })
    if not block:
        st = backend.query_status()
        return JSONResponse({
            'started': True,
            'op_id': op_id,
            'source': 'http',
            'started_at': st.started_at,
            'hint': '用 /game/status 查进度与结果',
        })
    result = await asyncio.wrap_future(future)
    msg = ('operation 运行成功' if result and result.success
           else f"operation 运行失败: {getattr(result, 'status', '无结果')}")
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

    @mcp.custom_route("/game/predefined-teams", methods=["GET"])
    async def _game_predefined_teams(request: Request) -> Response:
        """GET /game/predefined-teams 路由分发。"""
        return await handle_game_predefined_teams(backend, request)

    @mcp.custom_route("/game/run/one-dragon", methods=["POST"])
    async def _game_run_one_dragon(request: Request) -> Response:
        """POST /game/run/one-dragon 路由分发。"""
        return await handle_game_run_one_dragon(backend, request)

    @mcp.custom_route("/game/run/standalone", methods=["POST"])
    async def _game_run_standalone(request: Request) -> Response:
        """POST /game/run/standalone 路由分发。"""
        return await handle_game_run_standalone(backend, request)

    @mcp.custom_route("/game/operations", methods=["GET"])
    async def _game_operations(request: Request) -> Response:
        """GET /game/operations 路由分发。"""
        return await handle_game_operations(backend, request)

    @mcp.custom_route("/game/operations/describe", methods=["GET"])
    async def _game_operations_describe(request: Request) -> Response:
        """GET /game/operations/describe 路由分发。"""
        return await handle_game_operations_describe(backend, request)

    @mcp.custom_route("/game/run/operation", methods=["POST"])
    async def _game_run_operation(request: Request) -> Response:
        """POST /game/run/operation 路由分发。"""
        return await handle_game_run_operation(backend, request)
