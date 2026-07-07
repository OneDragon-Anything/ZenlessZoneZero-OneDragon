"""MCP 应用运行工具：一条龙、独立应用和应用列表。"""

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from zzz_od.backend.backend_context import ZzzBackendContext
from zzz_od.backend.schemas import ApplicationListResult

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_base import OperationResult


def make_run_one_dragon(backend: ZzzBackendContext) -> Callable:
    """构造 ``run_one_dragon`` tool。"""
    async def run_one_dragon(block: bool = False) -> dict | str:
        """按当前 GUI/配置的一条龙设置启动完整一条龙运行。

        block=False(默认)立刻返回,用 get_run_status 查进度;block=True 阻塞到结束。
        副作用:操作游戏并运行已启用的一条龙应用组;单跑道,已有运行时返回错误。
        """
        try:
            ok, future = backend.run_one_dragon('mcp')
        except Exception as e:  # noqa: BLE001 工具层兜底
            return {'started': False, 'error': str(e)}
        if not ok:
            # 并发拒绝时返回当前占用者信息，方便 agent 决定轮询还是停止。
            st = backend.query_status()
            return {
                'started': False,
                'error': '已有运行在进行中',
                'source': st.source,
                'hint': '先 get_run_status 查状态,或 stop_run 停止',
            }
        if not block:
            # 长耗时自动化默认不阻塞 MCP 调用，避免 agent 等待期间失去交互能力。
            st = backend.query_status()
            return {
                'started': True,
                'source': 'mcp',
                'app': st.app,
                'started_at': st.started_at,
                'hint': '用 get_run_status 查进度与结果',
            }
        # block=True 只返回最终摘要，不把运行日志塞进 tool 输出。
        result: OperationResult | None = await asyncio.wrap_future(future)
        if result is None:
            return '一条龙运行结束,但未返回结果'
        return '一条龙运行成功' if result.success else f'一条龙运行失败: {result.status}'
    return run_one_dragon


def make_run_standalone_app(backend: ZzzBackendContext) -> Callable:
    """构造 ``run_standalone_app`` tool。"""
    async def run_standalone_app(app_id: str | None = None, block: bool = False) -> dict | str:
        """启动独立应用。

        app_id 为空时使用 GUI「应用运行」当前选中的应用。block=False(默认)立刻返回,
        用 get_run_status 查进度;block=True 阻塞到结束。副作用:操作游戏并运行目标应用。
        """
        try:
            ok, future = backend.run_standalone_app('mcp', app_id=app_id)
        except Exception as e:  # noqa: BLE001 工具层兜底
            return {'started': False, 'error': str(e)}
        if not ok:
            # 并发拒绝时返回当前占用者信息，方便 agent 决定轮询还是停止。
            st = backend.query_status()
            return {
                'started': False,
                'error': '已有运行在进行中',
                'source': st.source,
                'hint': '先 get_run_status 查状态,或 stop_run 停止',
            }
        if not block:
            # 独立应用也可能跑很久，默认立刻返回并交给 get_run_status 轮询。
            st = backend.query_status()
            return {
                'started': True,
                'source': 'mcp',
                'app': st.app,
                'started_at': st.started_at,
                'hint': '用 get_run_status 查进度与结果',
            }
        # block=True 只返回最终摘要，不把运行日志塞进 tool 输出。
        result: OperationResult | None = await asyncio.wrap_future(future)
        if result is None:
            return '独立应用运行结束,但未返回结果'
        return '独立应用运行成功' if result.success else f'独立应用运行失败: {result.status}'
    return run_standalone_app


def make_list_applications(backend: ZzzBackendContext) -> Callable[[], ApplicationListResult]:
    """构造 ``list_applications`` tool。"""
    def list_applications() -> ApplicationListResult:
        """列出当前实例可运行应用、独立应用列表和当前选中项(无副作用)。"""
        return backend.list_applications()
    return list_applications
