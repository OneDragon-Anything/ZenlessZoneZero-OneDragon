from mcp.server.fastmcp import FastMCP

from .base import register_base_tools
from .game_operation import register_game_tools
from .screenshot import register_screenshot_tools
from .screen_analysis import register_screen_analysis_tools


def register_all_tools(mcp: FastMCP) -> None:
    """
    注册所有工具模块

    Args:
        mcp: FastMCP 服务器实例
    """
    register_base_tools(mcp)
    register_screenshot_tools(mcp)
    register_game_tools(mcp)
    register_screen_analysis_tools(mcp)
