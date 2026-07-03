"""HTTP 适配器：``/game/*`` 端点，把 ``ZzzBackendContext`` 暴露给 web/skill。

本模块在后端 game 切片（``ZzzBackendContext``）之上架设一层 HTTP 传输适配：
- ``register_http_routes`` 通过 FastMCP 的 ``custom_route`` 挂 7 个端点
  （``window``/``capture``/``analyze``/``enter``/``status``/``stop``/``close``），与 MCP ``/mcp``
  端点同进程共存。
- 7 个处理器函数（``handle_game_*``）为模块级、可独立调用，便于直接测试，
  不依赖 MCP 协议层；``capture`` 直接回传 PNG 字节，不落盘（区别于 MCP 适配器
  的落盘返路径，避免重复的 ``_save_screenshot`` 逻辑）。
- 同步 backend 方法通过 ``asyncio.to_thread`` 放到线程池执行，避免阻塞事件循环；
  ``enter`` 走 ``backend.start_run`` 异步派发，``block=true`` 时用
  ``asyncio.wrap_future`` 阻塞到运行结束。
"""

import asyncio
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from zzz_od.backend.backend_context import BackendNotReadyError, ZzzBackendContext


def _err(msg: str, status: int = 503) -> JSONResponse:
    """构造统一的错误 JSON 响应。

    Args:
        msg: 错误描述。
        status: HTTP 状态码，默认 503（服务未就绪）。

    Returns:
        body 为 ``{"error": msg}`` 的 ``JSONResponse``。
    """
    return JSONResponse({"error": msg}, status_code=status)


async def handle_game_window(backend: ZzzBackendContext, _request: Request | None = None) -> Response:
    """处理 ``GET /game/window``：返回游戏窗口状态 JSON。

    通过线程池调用 backend 的 ``check_window``，将其结构化结果序列化为 JSON。

    Args:
        backend: 提供游戏切片能力的 ``ZzzBackendContext``。
        _request: Starlette 请求对象（本处理器不使用，仅为对齐 custom_route 签名）。

    Returns:
        200 + 窗口状态 JSON；backend 未就绪时返回 503 + 错误描述。
    """
    try:
        status = await asyncio.to_thread(backend.check_window)
    except BackendNotReadyError as e:
        return _err(str(e))
    return JSONResponse(asdict(status))


async def handle_game_capture(backend: ZzzBackendContext, _request: Request | None = None) -> Response:
    """处理 ``GET /game/capture``：直接回传 PNG 字节。

    HTTP 适配器不落盘（区别于 MCP 适配器落盘返路径），将 RGB 截图转为 BGR 后
    编码为 PNG 字节直接作为响应体返回。

    Args:
        backend: 提供游戏切片能力的 ``ZzzBackendContext``。
        _request: Starlette 请求对象（本处理器不使用）。

    Returns:
        200 + ``image/png`` 字节流；backend 未就绪时返回 503，编码失败返回 500。
    """
    try:
        image = await asyncio.to_thread(backend.capture)
    except BackendNotReadyError as e:
        return _err(str(e))
    import cv2

    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        return _err("图像编码失败", status=500)
    return Response(bytes(buf), media_type="image/png")


async def handle_game_analyze(backend: ZzzBackendContext, _request: Request | None = None) -> Response:
    """处理 ``GET /game/analyze``：返回画面分析（截图 + OCR）结果 JSON。

    Args:
        backend: 提供游戏切片能力的 ``ZzzBackendContext``。
        _request: Starlette 请求对象（本处理器不使用）。

    Returns:
        200 + 分析结果 JSON（成功标志、OCR 文本列表、错误描述）；backend 未就绪时返回 503。
    """
    try:
        result = await asyncio.to_thread(backend.analyze)
    except BackendNotReadyError as e:
        return _err(str(e))
    return JSONResponse({
        "success": result.success,
        "ocr_texts": [asdict(t) for t in result.ocr_texts],
        "error": result.error,
    })


async def handle_game_enter(backend: ZzzBackendContext, request: Request | None = None) -> Response:
    """处理 ``POST /game/enter?block=``：打开并进入绝区零游戏。

    通过 ``backend.start_run('http', op_factory)`` 异步派发；``block=true``（默认）
    阻塞到运行结束并返回结果文本，``block=false`` 立刻返回已启动状态。

    Args:
        backend: 提供游戏切片能力的 ``ZzzBackendContext``。
        request: Starlette 请求对象，可携带 ``block`` query。

    Returns:
        200 + JSON：成功派发（block=true 时含运行结果文本；block=false 时含
        ``started_at``）；已有运行进行中时返回 ``started=False`` + 来源 + 提示。
    """
    block = True
    if request is not None:
        block = request.query_params.get('block', 'true').lower() != 'false'
    from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame

    ok, future = backend.start_run('http', lambda ctx: OpenAndEnterGame(ctx))
    if not ok:
        st = backend.query_status()
        return JSONResponse({'started': False, 'error': '已有运行在进行中',
                             'source': st.source, 'hint': '先 /game/status 查状态,或 /game/stop 停止'})
    if not block:
        st = backend.query_status()
        return JSONResponse({'started': True, 'source': 'http', 'started_at': st.started_at,
                             'hint': '用 /game/status 查进度与结果'})
    result = await asyncio.wrap_future(future)
    msg = '成功打开并进入绝区零游戏' if result.success else f'打开游戏失败: {result.status}'
    return JSONResponse({'result': msg})


async def handle_game_status(backend: ZzzBackendContext, _request: Request | None = None) -> Response:
    """处理 ``GET /game/status``：返回当前/最近运行状态 JSON。

    Args:
        backend: 提供游戏切片能力的 ``ZzzBackendContext``。
        _request: Starlette 请求对象（本处理器不使用）。

    Returns:
        200 + ``RunStatusResult`` 全字段 JSON。
    """
    return JSONResponse(asdict(backend.query_status()))


async def handle_game_stop(backend: ZzzBackendContext, _request: Request | None = None) -> Response:
    """处理 ``POST /game/stop``：发出停止信号。

    Args:
        backend: 提供游戏切片能力的 ``ZzzBackendContext``。
        _request: Starlette 请求对象（本处理器不使用）。

    Returns:
        200 + ``backend.stop()`` 返回的 JSON。
    """
    return JSONResponse(backend.stop())


async def handle_game_close(backend: ZzzBackendContext, _request: Request | None = None) -> Response:
    """处理 ``POST /game/close``：关闭游戏(发关闭窗口信号)。

    通过线程池调用 backend 的 ``close_game``，将其返回文本包装为 JSON。
    controller 吞异常不返成功标志，故响应仅表「信号已发」，用
    ``GET /game/window`` 验证是否真关。

    Args:
        backend: 提供游戏切片能力的 ``ZzzBackendContext``。
        _request: Starlette 请求对象（本处理器不使用）。

    Returns:
        200 + ``{"result": <文本>}``；backend 未就绪时返回 503 + 错误描述。
    """
    try:
        msg = await asyncio.to_thread(backend.close_game)
    except BackendNotReadyError as e:
        return _err(str(e))
    return JSONResponse({"result": msg})


def register_http_routes(mcp: FastMCP, backend: ZzzBackendContext) -> None:
    """把 ``/game/*`` 端点挂到 FastMCP。

    使用 ``custom_route``（装饰器工厂二次调用）在 Starlette 层挂载 7 个端点，
    与 MCP ``/mcp`` 同进程共存。通过闭包将 ``backend`` 注入到各 lambda 处理器。

    Args:
        mcp: 目标 ``FastMCP`` 实例。
        backend: 已就绪的 ``ZzzBackendContext``，提供 game 切片能力。
    """
    @mcp.custom_route("/game/window", methods=["GET"])
    async def _game_window(request: Request) -> Response:
        """GET /game/window 路由分发：委托 ``handle_game_window``。"""
        return await handle_game_window(backend, request)

    @mcp.custom_route("/game/capture", methods=["GET"])
    async def _game_capture(request: Request) -> Response:
        """GET /game/capture 路由分发：委托 ``handle_game_capture``。"""
        return await handle_game_capture(backend, request)

    @mcp.custom_route("/game/analyze", methods=["GET"])
    async def _game_analyze(request: Request) -> Response:
        """GET /game/analyze 路由分发：委托 ``handle_game_analyze``。"""
        return await handle_game_analyze(backend, request)

    @mcp.custom_route("/game/enter", methods=["POST"])
    async def _game_enter(request: Request) -> Response:
        """POST /game/enter 路由分发：委托 ``handle_game_enter``。"""
        return await handle_game_enter(backend, request)

    @mcp.custom_route("/game/status", methods=["GET"])
    async def _game_status(request: Request) -> Response:
        """GET /game/status 路由分发：委托 ``handle_game_status``。"""
        return await handle_game_status(backend, request)

    @mcp.custom_route("/game/stop", methods=["POST"])
    async def _game_stop(request: Request) -> Response:
        """POST /game/stop 路由分发：委托 ``handle_game_stop``。"""
        return await handle_game_stop(backend, request)

    @mcp.custom_route("/game/close", methods=["POST"])
    async def _game_close(request: Request) -> Response:
        """POST /game/close 路由分发：委托 ``handle_game_close``。"""
        return await handle_game_close(backend, request)
