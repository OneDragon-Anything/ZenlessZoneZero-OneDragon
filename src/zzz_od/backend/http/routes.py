"""HTTP 适配器：``/game/*`` 端点，把 ``ZzzBackendContext`` 暴露给 web/skill。

本模块在后端 game 切片（``ZzzBackendContext``）之上架设一层 HTTP 传输适配：
- ``register_http_routes`` 通过 FastMCP 的 ``custom_route`` 挂 4 个端点
  （``window``/``capture``/``analyze``/``enter``），与 MCP ``/mcp`` 端点同进程共存。
- 4 个处理器函数（``handle_game_*``）为模块级、可独立调用，便于直接测试，
  不依赖 MCP 协议层；``capture`` 直接回传 PNG 字节，不落盘（区别于 MCP 适配器
  的落盘返路径，避免重复的 ``_save_screenshot`` 逻辑）。
- 同步 backend 方法通过 ``asyncio.to_thread`` 放到线程池执行，避免阻塞事件循环。
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


async def handle_game_enter(backend: ZzzBackendContext, _request: Request | None = None) -> Response:
    """处理 ``POST /game/enter``：打开并进入绝区零游戏。

    长阻塞流程，通过线程池调用 backend 的同步 ``enter_game``，避免阻塞事件循环。

    Args:
        backend: 提供游戏切片能力的 ``ZzzBackendContext``。
        _request: Starlette 请求对象（本处理器不使用）。

    Returns:
        200 + ``{"result": msg}``；backend 未就绪时返回 503。
    """
    try:
        msg = await asyncio.to_thread(backend.enter_game)
    except BackendNotReadyError as e:
        return _err(str(e))
    return JSONResponse({"result": msg})


def register_http_routes(mcp: FastMCP, backend: ZzzBackendContext) -> None:
    """把 ``/game/*`` 端点挂到 FastMCP。

    使用 ``custom_route``（装饰器工厂二次调用）在 Starlette 层挂载 4 个端点，
    与 MCP ``/mcp`` 同进程共存。通过闭包将 ``backend`` 注入到各 lambda 处理器。

    Args:
        mcp: 目标 ``FastMCP`` 实例。
        backend: 已就绪的 ``ZzzBackendContext``，提供 game 切片能力。
    """
    mcp.custom_route("/game/window", methods=["GET"])(
        lambda request: handle_game_window(backend, request)
    )
    mcp.custom_route("/game/capture", methods=["GET"])(
        lambda request: handle_game_capture(backend, request)
    )
    mcp.custom_route("/game/analyze", methods=["GET"])(
        lambda request: handle_game_analyze(backend, request)
    )
    mcp.custom_route("/game/enter", methods=["POST"])(
        lambda request: handle_game_enter(backend, request)
    )
