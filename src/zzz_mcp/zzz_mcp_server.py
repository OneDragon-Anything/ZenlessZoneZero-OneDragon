"""
ZZZ MCP Server - 绝区零游戏画面感知MCP服务器

提供游戏截图、画面识别等功能，用于游戏内容更新后的适配工作。
"""
import sys

import uvicorn
from mcp.server.fastmcp import FastMCP

from zzz_mcp.context import zzz_lifespan
from zzz_mcp.tools import register_all_tools

# 创建MCP服务器实例，传入 lifespan 管理 ZContext
mcp = FastMCP("zzz_od", lifespan=zzz_lifespan)

# 注册所有工具
register_all_tools(mcp)


def main(host: str = "127.0.0.1", port: int = 8000):
    """
    启动MCP服务器

    Args:
        host: 监听地址
        port: 监听端口
    """
    print("=" * 60)
    print("ZZZ OD MCP Server (HTTP传输方式)")
    print("=" * 60)
    print(f"\n监听地址: http://{host}:{port}/mcp")
    print("\n按 Ctrl+C 停止服务器\n")
    print("-" * 60)

    # 获取Starlette应用并使用uvicorn运行
    app = mcp.streamable_http_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="启动ZZZ OD MCP服务器（HTTP传输方式）"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="监听地址 (默认: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="监听端口 (默认: 8000)"
    )

    args = parser.parse_args()

    try:
        main(host=args.host, port=args.port)
    except KeyboardInterrupt:
        print("\n\n服务器已停止")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] 服务器启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
