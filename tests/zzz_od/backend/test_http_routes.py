"""HTTP ``/game/*`` 适配器的单元测试。

直接 await 处理器函数，避开 MCP 协议层；backend 使用 ``MagicMock`` 伪造，
避免依赖真实游戏窗口与 ``ZContext``。``capture`` 用例给真实 numpy 图（可编码），
以验证 PNG 字节回传链路。
"""

import json
from unittest.mock import MagicMock

import pytest

from zzz_od.backend.backend_context import BackendNotReadyError
from zzz_od.backend.http.routes import (
    handle_game_analyze,
    handle_game_capture,
    handle_game_enter,
    handle_game_window,
)
from zzz_od.backend.schemas import AnalyzeScreenResult, WindowStatus


@pytest.mark.asyncio
async def test_handle_game_window_ok() -> None:
    """handle_game_window 在就绪时应以 200 返回窗口状态 JSON。"""
    backend = MagicMock()
    backend.check_window.return_value = WindowStatus(
        win_title="绝区零", is_win_valid=True, is_win_active=False, is_win_scale=True, x=1, y=2, width=3, height=4
    )
    resp = await handle_game_window(backend)
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert data["win_title"] == "绝区零"
    assert data["x"] == 1


@pytest.mark.asyncio
async def test_handle_game_window_error() -> None:
    """handle_game_window 在 backend 未就绪时应返回 503。"""
    backend = MagicMock()
    backend.check_window.side_effect = BackendNotReadyError("未就绪")
    resp = await handle_game_window(backend)
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_handle_game_capture_returns_png_bytes() -> None:
    """handle_game_capture 应直接回传 PNG 字节（media_type=image/png，不落盘）。"""
    import numpy as np

    backend = MagicMock()
    backend.capture.return_value = np.zeros((1, 1, 3), dtype="uint8")  # 可编码的 1x1 RGB 图
    resp = await handle_game_capture(backend)
    assert resp.status_code == 200
    assert resp.media_type == "image/png"
    assert resp.body[:4] == b"\x89PNG"  # PNG magic


@pytest.mark.asyncio
async def test_handle_game_analyze_ok() -> None:
    """handle_game_analyze 在成功时应以 200 返回分析结果 JSON。"""
    backend = MagicMock()
    backend.analyze.return_value = AnalyzeScreenResult(success=True, ocr_texts=[], error=None)
    resp = await handle_game_analyze(backend)
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert data["success"] is True


@pytest.mark.asyncio
async def test_handle_game_enter_ok() -> None:
    """handle_game_enter 应以 200 返回 enter_game 的结果字符串。"""
    backend = MagicMock()
    backend.enter_game.return_value = "成功打开并进入绝区零游戏"
    resp = await handle_game_enter(backend)
    assert resp.status_code == 200
    assert "成功" in resp.body.decode("utf-8")


def test_register_http_routes_adds_custom_routes() -> None:
    """register_http_routes 应在 FastMCP 上挂载 /game/* 路由。"""
    from mcp.server.fastmcp import FastMCP

    from zzz_od.backend.http.routes import register_http_routes

    mcp = FastMCP("test")
    register_http_routes(mcp, MagicMock())
    # custom_route 挂在 Starlette 层；用 streamable_http_app 的 routes 校验
    app = mcp.streamable_http_app()
    paths = {getattr(r, "path", None) for r in app.routes}
    assert any(p and "game" in p for p in paths)
