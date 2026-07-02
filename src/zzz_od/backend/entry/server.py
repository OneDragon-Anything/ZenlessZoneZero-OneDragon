"""后端服务入口：装配 backend + MCP + HTTP，由 uvicorn 运行。

本模块把 Task 4（MCP 适配器）与 Task 5（HTTP ``/game/*`` 适配器）装配到同一个
``FastMCP`` 实例上，并通过 ``streamable_http_app()`` 得到一个 Starlette app，
最终交给 uvicorn 在单进程内并行对外提供 MCP（``/mcp``）与 HTTP（``/game/*``）服务。
"""

import argparse
import asyncio
from typing import TYPE_CHECKING

import uvicorn

from one_dragon.utils.log_utils import log
from zzz_od.backend.backend_context import ZzzBackendContext
from zzz_od.backend.http.routes import register_http_routes
from zzz_od.backend.mcp.app import create_mcp_server
from zzz_od.context.zzz_context import ZContext

if TYPE_CHECKING:
    from starlette.applications import Starlette

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 23001


def create_app(backend: ZzzBackendContext) -> "Starlette":
    """装配应用：同一 FastMCP 同时挂 MCP tool 与 ``/game/*`` custom_route。

    先创建 MCP 服务器（注册 4 个 game 工具），再把 ``/game/*`` HTTP 端点挂到
    同一实例上，最后返回 ``streamable_http_app()`` 产生的 Starlette app。
    这样 MCP ``/mcp`` 端点与 HTTP ``/game/*`` 端点同进程、同 app 共存。

    Args:
        backend: 已就绪的 ``ZzzBackendContext``，提供 game 切片能力。

    Returns:
        挂载好 MCP 与 ``/game/*`` 路由的 Starlette 应用。
    """
    mcp = create_mcp_server(backend)
    register_http_routes(mcp, backend)
    return mcp.streamable_http_app()


async def _serve(host: str, port: int) -> None:
    """启动后端服务：初始化 backend → 装配 app → uvicorn 运行。

    构造 ``ZContext`` 与 ``ZzzBackendContext``，在线程池中完成 ``ZContext`` 的
    同步初始化（``backend.start()``，不阻塞事件循环），随后装配 app 并交给
    uvicorn 持续对外服务；无论正常退出还是异常，最终都会调用 ``backend.shutdown()``
    释放资源。

    Args:
        host: 监听地址。
        port: 监听端口。
    """
    ctx = ZContext()
    backend = ZzzBackendContext(ctx)
    try:
        log.info("ZZZ 后端：初始化 ZContext（线程池，不阻塞事件循环）……")
        await backend.start()
        app = create_app(backend)
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        log.info(f"ZZZ 后端监听: http://{host}:{port}/mcp 与 /game/*")
        await server.serve()
    finally:
        await backend.shutdown()


def main() -> None:
    """命令行入口：解析参数并启动后端服务。

    通过 argparse 解析 ``--host`` / ``--port``（默认 ``127.0.0.1`` / ``23001``），
    随后 ``asyncio.run`` 驱动 ``_serve`` 完成整个生命周期。
    """
    parser = argparse.ArgumentParser(description="启动 ZZZ 后端服务（MCP + HTTP）")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口")
    args = parser.parse_args()
    asyncio.run(_serve(args.host, args.port))


if __name__ == "__main__":
    main()
