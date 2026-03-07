"""
游戏操作工具模块

提供游戏启动、操作相关的 MCP 工具。
"""
from mcp.server.fastmcp import FastMCP

from ..context import get_zzz_context


def register_game_tools(mcp: FastMCP) -> None:
    """注册游戏操作工具"""

    @mcp.tool()
    def open_and_enter_game() -> str:
        """
        打开并进入绝区零游戏

        注意：
        1. 此操作需要较长时间（可能需要1-2分钟）
        2. 执行步骤：启动运行上下文 → 打开游戏客户端 → 等待窗口初始化 → 自动登录
        3. ⚠️ 环境要求：
           - 不支持远程桌面/SSH 会话环境（如 RDP、frps、SSH隧道）
           - 游戏会检测运行环境，在远程会话下无法创建可见窗口
           - 建议在本地交互式会话中使用，或先手动启动游戏再使用其他工具

        操作流程：
        1. 关闭自动HDR
        2. 启动游戏进程
        3. 等待游戏窗口就绪（最多60秒）
        4. 恢复HDR设置
        5. 执行登录操作

        Returns:
            str: 操作结果信息
        """
        zzz = get_zzz_context()
        if zzz is None:
            return "错误: ZContext 未初始化"

        from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame
        from one_dragon.utils.log_utils import log

        try:
            log.info("MCP: 开始执行打开并进入游戏操作")

            # 启动运行上下文
            if not zzz.run_context.start_running():
                return "错误: 无法启动运行上下文，请检查控制器是否已初始化"

            try:
                # 设置运行上下文属性（参考 suibian_temple_craft_dispatch.py 的示例）
                zzz.run_context.current_instance_idx = zzz.current_instance_idx

                # 执行打开并进入游戏操作
                op = OpenAndEnterGame(zzz)
                result = op.execute()

                if result.success:
                    return "成功打开并进入绝区零游戏"
                else:
                    return f"打开游戏失败: {result.status}"
            finally:
                # 停止运行上下文（重要：确保资源正确释放）
                zzz.run_context.stop_running()

        except Exception as e:
            log.error(f"MCP: 打开游戏时发生错误: {e}", exc_info=True)
            return f"打开游戏时发生错误: {str(e)}"
