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
    handle_game_close,
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
async def test_handle_game_analyze_returns_screens() -> None:
    """HTTP /game/analyze 返回 JSON 含 screens 嵌套;area_type 经 asdict+json 序列化为 'text'。"""
    from one_dragon.base.screen.screen_match import (
        AreaMatchDetail,
        AreaType,
        ScreenMatch,
    )

    detail = AreaMatchDetail(
        area_name='标题', area_type=AreaType.TEXT,
        x=1, y=1, width=1, height=1, text='菜单', confidence=0.9,
    )
    match = ScreenMatch(screen_name='菜单', is_precise=True, areas=[detail])
    backend = MagicMock()
    backend.analyze.return_value = AnalyzeScreenResult(
        success=True, ocr_texts=[], error=None, screens=[match])
    resp = await handle_game_analyze(backend)  # _request 默认 None,处理器不读 request
    assert resp.status_code == 200
    body = json.loads(resp.body.decode('utf-8'))
    assert body['success'] is True
    assert body['screens'][0]['screen_name'] == '菜单'
    # str Enum 经 asdict 保 Enum 对象、json.dumps 序列化为 'text';与 AreaType.TEXT('text') 相等
    assert body['screens'][0]['areas'][0]['area_type'] == AreaType.TEXT


@pytest.mark.asyncio
async def test_handle_game_enter_ok() -> None:
    """handle_game_enter 应委托 backend.start_run，返回 started/result JSON。

    block=true（默认）且 start_run 返回 (True, 已完成 Future) 时，
    响应体应包含 result 文本（success → 「成功打开并进入绝区零游戏」）。
    """
    from concurrent.futures import Future
    from dataclasses import dataclass

    from zzz_od.backend.schemas import RunStatusResult

    @dataclass
    class _FakeRequest:
        query_params: dict

        async def json(self) -> dict:
            return {}

    @dataclass
    class _OpResult:
        success: bool
        status: str = ""

    fut: Future = Future()
    fut.set_result(_OpResult(success=True))
    backend = MagicMock()
    backend.start_run.return_value = (True, fut)
    backend.query_status.return_value = RunStatusResult(
        state="running", source="http", app="OpenAndEnterGame",
        started_at="2026-07-02T00:00:00", duration_seconds=1.0,
    )
    resp = await handle_game_enter(backend, _FakeRequest({}))
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert data["result"] == "成功打开并进入绝区零游戏"
    backend.start_run.assert_called_once()


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


@pytest.mark.asyncio
async def test_handle_game_close_ok() -> None:
    """handle_game_close 在就绪时应以 200 返回 backend.close_game() 文本。"""
    backend = MagicMock()
    backend.close_game.return_value = "已发送关闭游戏信号,可用 check_game_window 验证"
    resp = await handle_game_close(backend)
    assert resp.status_code == 200
    data = json.loads(resp.body.decode("utf-8"))
    assert data["result"] == "已发送关闭游戏信号,可用 check_game_window 验证"


@pytest.mark.asyncio
async def test_handle_game_close_error() -> None:
    """handle_game_close 在 backend 未就绪时应返回 503。"""
    backend = MagicMock()
    backend.close_game.side_effect = BackendNotReadyError("未就绪")
    resp = await handle_game_close(backend)
    assert resp.status_code == 503


def test_route_dispatch_game_close_ok() -> None:
    """经路由层分发 POST /game/close,应返回 200 + result 文本。"""
    from mcp.server.fastmcp import FastMCP
    from starlette.testclient import TestClient

    from zzz_od.backend.http.routes import register_http_routes

    mcp = FastMCP("test")
    backend = MagicMock()
    backend.close_game.return_value = "已发送关闭游戏信号,可用 check_game_window 验证"
    register_http_routes(mcp, backend)
    client = TestClient(mcp.streamable_http_app())
    resp = client.post("/game/close")
    assert resp.status_code == 200
    assert resp.json()["result"] == "已发送关闭游戏信号,可用 check_game_window 验证"


def test_route_dispatch_window_ok() -> None:
    """经 Starlette 路由层分发 GET /game/window，应返回 200 + 窗口状态 JSON。

    回归 ``register_http_routes`` 中同步 lambda 返回 coroutine 的 bug：
    处理器未走真实路由分发，上面几个直调 ``handle_*`` 的用例无法覆盖。
    """
    from mcp.server.fastmcp import FastMCP
    from starlette.testclient import TestClient

    from zzz_od.backend.http.routes import register_http_routes

    mcp = FastMCP("test")
    backend = MagicMock()
    backend.check_window.return_value = WindowStatus(
        win_title="绝区零", is_win_valid=True, is_win_active=False, is_win_scale=True
    )
    register_http_routes(mcp, backend)
    client = TestClient(mcp.streamable_http_app())
    resp = client.get("/game/window")
    assert resp.status_code == 200
    assert resp.json()["win_title"] == "绝区零"


def test_route_dispatch_window_not_ready() -> None:
    """经路由层分发，backend 未就绪时应返回 503（而非 500）。"""
    from mcp.server.fastmcp import FastMCP
    from starlette.testclient import TestClient

    from zzz_od.backend.http.routes import register_http_routes

    mcp = FastMCP("test")
    backend = MagicMock()
    backend.check_window.side_effect = BackendNotReadyError("未就绪")
    register_http_routes(mcp, backend)
    client = TestClient(mcp.streamable_http_app())
    resp = client.get("/game/window")
    assert resp.status_code == 503
