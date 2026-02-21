# -*- coding: utf-8 -*-
"""
测试游戏启动工具功能

用于诊断 MCP 启动游戏工具失败的问题。
"""

import unittest
import asyncio
from unittest.mock import MagicMock, patch


class TestGameOperationBasic(unittest.TestCase):
    """基础模块导入测试"""

    def test_import_zzz_mcp_modules(self):
        """测试能否导入 zzz_mcp 模块"""
        from zzz_mcp.context import get_zzz_context
        self.assertIsNotNone(get_zzz_context)

    def test_import_zzz_od_modules(self):
        """测试能否导入 zzz_od 模块"""
        from zzz_od.context.zzz_context import ZContext
        self.assertIsNotNone(ZContext)

    def test_get_zzz_context_when_not_initialized(self):
        """测试未初始化时获取上下文"""
        from zzz_mcp.context import get_zzz_context
        ctx = get_zzz_context()
        self.assertIsNone(ctx, "未初始化时应返回 None")


class TestGameOperationContext(unittest.TestCase):
    """测试 ZContext 初始化和状态"""

    def setUp(self):
        """每个测试前重置全局上下文"""
        import zzz_mcp.context as ctx_module
        ctx_module._zzz_context = None

    def tearDown(self):
        """每个测试后清理全局上下文"""
        import zzz_mcp.context as ctx_module
        ctx_module._zzz_context = None

    def test_zzz_lifespan_initialization(self):
        """测试 ZContext 通过 lifespan 初始化"""
        from zzz_mcp.context import zzz_lifespan, McpContext
        from mcp.server.fastmcp import FastMCP

        async def test():
            mock_mcp = MagicMock()

            async with zzz_lifespan(mock_mcp) as context:
                self.assertIsInstance(context, McpContext)
                self.assertIsNotNone(context.zzz)
                print(f"ZContext 初始化成功，ready_for_application: {context.zzz.ready_for_application}")
                print(f"Controller 类型: {type(context.zzz.controller).__name__}")
                print(f"RunContext 类型: {type(context.zzz.run_context).__name__}")

        asyncio.run(test())

    def test_zzz_context_controller(self):
        """测试 Controller 是否正确初始化"""
        from zzz_mcp.context import zzz_lifespan
        from mcp.server.fastmcp import FastMCP

        async def test():
            mock_mcp = MagicMock()

            async with zzz_lifespan(mock_mcp) as context:
                ctx = context.zzz
                self.assertIsNotNone(ctx.controller, "Controller 不应为 None")
                print(f"Controller 实例: {ctx.controller}")

                # 检查关键方法
                self.assertTrue(hasattr(ctx.controller, 'init_game_win'), "应有 init_game_win 方法")
                self.assertTrue(hasattr(ctx.controller, 'is_game_window_ready'), "应有 is_game_window_ready 属性")

        asyncio.run(test())

    def test_zzz_context_run_context(self):
        """测试 RunContext 是否正确初始化"""
        from zzz_mcp.context import zzz_lifespan
        from mcp.server.fastmcp import FastMCP

        async def test():
            mock_mcp = MagicMock()

            async with zzz_lifespan(mock_mcp) as context:
                ctx = context.zzz
                self.assertIsNotNone(ctx.run_context, "RunContext 不应为 None")
                print(f"RunContext 实例: {ctx.run_context}")

                # 检查关键方法
                self.assertTrue(hasattr(ctx.run_context, 'start_running'), "应有 start_running 方法")
                self.assertTrue(hasattr(ctx.run_context, 'stop_running'), "应有 stop_running 方法")

        asyncio.run(test())


class TestGameOperationTool(unittest.TestCase):
    """测试游戏启动工具"""

    def setUp(self):
        """每个测试前重置全局上下文"""
        import zzz_mcp.context as ctx_module
        ctx_module._zzz_context = None

    def tearDown(self):
        """每个测试后清理全局上下文"""
        import zzz_mcp.context as ctx_module
        ctx_module._zzz_context = None

    def test_register_game_tools(self):
        """测试游戏工具注册"""
        from zzz_mcp.tools.game_operation import register_game_tools
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test_server")
        register_game_tools(mcp)

        tools = mcp._tool_manager._tools
        self.assertIn("open_and_enter_game", tools)

    def test_open_and_enter_game_without_context(self):
        """测试在没有 ZContext 时调用打开游戏"""
        from zzz_mcp.tools.game_operation import register_game_tools
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test_server")
        register_game_tools(mcp)

        tools = mcp._tool_manager._tools
        open_game_tool = tools["open_and_enter_game"]

        result = open_game_tool.fn()
        self.assertIn("错误", result)
        self.assertIn("未初始化", result)

    @patch('one_dragon.base.operation.application.application_run_context.ApplicationRunContext.start_running')
    def test_open_and_enter_game_run_context_fails(self, mock_start_running):
        """测试 run_context 启动失败"""
        from zzz_mcp.context import zzz_lifespan
        from zzz_mcp.tools.game_operation import register_game_tools
        from mcp.server.fastmcp import FastMCP

        # 模拟 start_running 返回 False
        mock_start_running.return_value = False

        async def test():
            mock_mcp = MagicMock()

            async with zzz_lifespan(mock_mcp) as context:
                # 注册工具（使用新的 MCP 实例）
                test_mcp = FastMCP("test_server")
                register_game_tools(test_mcp)

                tools = test_mcp._tool_manager._tools
                open_game_tool = tools["open_and_enter_game"]

                result = open_game_tool.fn()
                print(f"结果: {result}")

                self.assertIn("错误", result)
                self.assertIn("启动运行上下文", result)

        asyncio.run(test())

    @unittest.skip("集成测试：需要实际的游戏环境，跳过自动运行")
    def test_open_and_enter_game_integration(self):
        """集成测试：实际测试打开游戏流程"""
        from zzz_mcp.context import zzz_lifespan
        from zzz_mcp.tools.game_operation import register_game_tools
        from mcp.server.fastmcp import FastMCP
        import time

        async def test():
            mock_mcp = MagicMock()

            async with zzz_lifespan(mock_mcp) as context:
                # 注册工具
                test_mcp = FastMCP("test_server")
                register_game_tools(test_mcp)

                tools = test_mcp._tool_manager._tools
                open_game_tool = tools["open_and_enter_game"]

                # 实际执行打开游戏（这将花费较长时间）
                print("开始执行打开游戏操作...")
                start_time = time.time()
                result = open_game_tool.fn()
                elapsed_time = time.time() - start_time

                print(f"操作结果: {result}")
                print(f"耗时: {elapsed_time:.2f} 秒")

                # 验证结果
                self.assertNotIn("错误", result, "不应该有错误")

        asyncio.run(test())
