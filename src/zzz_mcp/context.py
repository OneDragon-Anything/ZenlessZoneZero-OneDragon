"""
MCP 服务器上下文管理

管理 ZContext 的生命周期，为所有 MCP 工具提供共享的游戏上下文。
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from zzz_od.context.zzz_context import ZContext

# 全局 ZContext 实例
_zzz_context: ZContext | None = None


@dataclass
class McpContext:
    """MCP 服务器应用上下文，包装 ZContext 实例"""
    zzz: ZContext


def get_zzz_context() -> ZContext | None:
    """
    获取全局 ZContext 实例

    Returns:
        ZContext | None: 全局 ZContext 实例，如果未初始化则返回 None
    """
    return _zzz_context


@asynccontextmanager
async def zzz_lifespan(server: FastMCP) -> AsyncIterator[McpContext]:
    """
    管理 ZContext 的生命周期

    在服务器启动时初始化 ZContext，在服务器关闭时清理资源。

    Args:
        server: FastMCP 服务器实例

    Yields:
        McpContext: 包含初始化后的 ZContext 的应用上下文
    """
    global _zzz_context
    from one_dragon.utils.log_utils import log
    log.info("ZZZ MCP Server: Initializing ZContext...")
    ctx = ZContext()
    _zzz_context = ctx
    try:
        # 初始化 ZContext（参考 app.py 的使用方式）
        ctx.init()
        log.info(f"ZZZ MCP Server: ZContext initialized. Ready: {ctx.ready_for_application}")
        yield McpContext(zzz=ctx)
    finally:
        # 清理资源
        log.info("ZZZ MCP Server: Shutting down ZContext...")
        _zzz_context = None
        ctx.after_app_shutdown()
        log.info("ZZZ MCP Server: ZContext shutdown complete")
