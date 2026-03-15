"""
基础工具模块

提供基础的 MCP 工具，如 ping、status 等。
"""
from mcp.server.fastmcp import FastMCP

from ..context import get_zzz_context


def register_base_tools(mcp: FastMCP) -> None:
    """注册基础工具"""

    @mcp.tool()
    def check_game_window() -> str:
        """
        检查绝区零游戏窗口状态

        Returns:
            str: 游戏窗口状态信息，包括窗口标题、有效性、激活状态、位置和大小
        """
        zzz = get_zzz_context()
        if zzz is None:
            return "错误: ZContext 未初始化"

        if zzz.controller is None:
            return "错误: 控制器未初始化"

        game_win = zzz.controller.game_win
        if game_win is None:
            return "错误: 游戏窗口未初始化"

        status_lines = [
            "游戏窗口状态:",
            f"  窗口标题: {game_win.win_title}",
            f"  窗口有效: {game_win.is_win_valid}",
            f"  窗口激活: {game_win.is_win_active}",
            f"  窗口缩放: {game_win.is_win_scale}",
        ]

        if game_win.win_rect is not None:
            rect = game_win.win_rect
            status_lines.append(f"  窗口位置: x={rect.x1}, y={rect.y1}, 宽={rect.width}, 高={rect.height}")

        return "\n".join(status_lines)
