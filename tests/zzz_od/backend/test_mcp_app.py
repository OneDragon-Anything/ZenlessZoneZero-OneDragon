"""MCP 适配器的单元测试。

测试使用 MagicMock 伪造 backend，避免依赖真实游戏窗口与 ZContext。
通过 FastMCP 的 ``_tool_manager._tools`` 探测已注册的工具，并直接调用其
``Tool.fn`` 验证行为（已注册 ``Tool`` 的可调用对象属性为 ``fn``）。
"""

from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

from zzz_od.backend.backend_context import BackendNotReadyError
from zzz_od.backend.mcp.app import create_mcp_server
from zzz_od.backend.schemas import AnalyzeScreenResult, WindowStatus


def _mcp_with_backend() -> tuple[FastMCP, MagicMock]:
    """构造一个 MCP 服务器与对应的伪造 backend。

    Returns:
        ``(mcp, backend)`` 元组：mcp 为注册了 6 个工具的 FastMCP 实例
        （check/capture/analyze + open_and_enter_game/get_run_status/stop_run），
        backend 为 MagicMock，可在测试中配置其方法返回值或副作用。
    """
    backend = MagicMock()
    mcp = create_mcp_server(backend)
    return mcp, backend


def test_registers_all_tools() -> None:
    """create_mcp_server 应注册 6 个 game 工具。"""
    mcp, _ = _mcp_with_backend()
    names = set(mcp._tool_manager._tools.keys())
    assert {
        "check_game_window",
        "capture_game_screen",
        "analyze_screen",
        "open_and_enter_game",
        "get_run_status",
        "stop_run",
    } <= names


def test_check_game_window_tool_error_on_not_ready() -> None:
    """check_game_window 在 backend 未就绪时返回包含「错误」的字符串。"""
    mcp, backend = _mcp_with_backend()
    backend.check_window.side_effect = BackendNotReadyError("未就绪")
    tool = mcp._tool_manager._tools["check_game_window"]
    # FastMCP 工具实际可调用对象在 .fn / .func；按版本取能 call 的那个
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    assert fn is not None
    out = fn()
    assert "错误" in out


def test_analyze_tool_returns_result() -> None:
    """analyze_screen 应直接返回 backend.analyze() 的结果。"""
    mcp, backend = _mcp_with_backend()
    backend.analyze.return_value = AnalyzeScreenResult(success=True, ocr_texts=[], error=None)
    tool = mcp._tool_manager._tools["analyze_screen"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    result = fn()
    assert result.success is True


def test_check_game_window_formats_status() -> None:
    """check_game_window 在就绪时应格式化输出窗口状态字段。"""
    mcp, backend = _mcp_with_backend()
    backend.check_window.return_value = WindowStatus(
        win_title="ZenlessZoneZero",
        is_win_valid=True,
        is_win_active=False,
        is_win_scale=True,
        x=10,
        y=20,
        width=1920,
        height=1080,
    )
    tool = mcp._tool_manager._tools["check_game_window"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    out = fn()
    assert "ZenlessZoneZero" in out
    assert "x=10" in out


def test_capture_game_screen_returns_path() -> None:
    """capture_game_screen 应保存截图并返回保存路径字符串。"""
    import numpy as np

    mcp, backend = _mcp_with_backend()
    backend.capture.return_value = np.zeros((4, 4, 3), dtype=np.uint8)
    tool = mcp._tool_manager._tools["capture_game_screen"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    path = fn()
    assert isinstance(path, str)
    assert path.endswith(".png")
