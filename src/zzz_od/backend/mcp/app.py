"""MCP 适配器：把 ``ZzzBackendContext`` 以 MCP tool 的形式对外暴露。

本模块在后端 game 切片（``ZzzBackendContext``）之上架设一层传输适配：
- ``create_mcp_server`` 创建一个 ``FastMCP`` 实例，并通过闭包将 backend 注入到
  工具函数中，使工具调用最终落到 backend 的 game 切片方法上。
- 工具返回值尽量保持「可直接读」的字符串或传输无关结构，便于上层（CLI/Agent）消费。

注意：
    - 同步工具（check/capture/analyze）直接调用 backend 的同步方法；
    - ``open_and_enter_game`` 为异步长耗时操作，基于 ``backend.start_run`` 适配，
      ``block=True`` 阻塞到完成、``block=False`` 立刻返回。
    - 运行类 tool 工厂（``make_open_and_enter_game`` 等）为模块级函数，
      只调 backend 公开方法，不戳 run_slot 私有，便于独立测试。
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log
from zzz_od.backend.backend_context import ZzzBackendContext
from zzz_od.backend.schemas import AnalyzeScreenResult, RunStatusResult

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.operation.operation_base import OperationResult


def _save_screenshot(image: 'MatLike') -> str:
    """将 RGB 截图以 BGR 写盘，返回绝对路径。

    Args:
        image: backend ``capture`` 返回的 RGB ``ndarray``。

    Returns:
        保存后的截图文件绝对路径。
    """
    import cv2

    screenshot_dir = Path(os_utils.get_path_under_work_dir(".debug", "zzz_od_mcp", "screenshot"))
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    img_path = screenshot_dir / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    bgr_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if not cv2.imwrite(str(img_path), bgr_image):
        raise RuntimeError(f"截图写盘失败: {img_path}")
    return str(img_path)


def make_open_and_enter_game(backend: ZzzBackendContext) -> Callable:
    """构造 ``open_and_enter_game`` tool(模块级,便于独立测试)。

    返回的 async tool 只调 backend 公开方法(``start_run``/``query_status``),
    不戳 run_slot 私有(P11 对称 + 封装)。
    """
    async def open_and_enter_game(block: bool = True) -> dict | str:
        """打开并进入绝区零游戏(长耗时,需交互式桌面)。

        block=True(默认)阻塞到完成返结果文本;block=False 立刻返回,用 get_run_status 查进度。
        副作用:操作游戏(点击/按键);单跑道,已有运行时返回错误(含 source + 提示)。
        中断语义:block=True 时若调用方取消 await,底层 operation 仍继续(结果入槽),
        用 get_run_status 查;中断的只是本次 await,不影响后台 _run。
        """
        from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame
        ok, future = backend.start_run('mcp', lambda ctx: OpenAndEnterGame(ctx))
        if not ok:
            st = backend.query_status()
            return {
                'started': False,
                'error': '已有运行在进行中',
                'source': st.source,
                'hint': '先 get_run_status 查状态,或 stop_run 停止',
            }
        if not block:
            st = backend.query_status()
            return {
                'started': True,
                'source': 'mcp',
                'started_at': st.started_at,
                'hint': '用 get_run_status 查进度与结果',
            }
        result: OperationResult = await asyncio.wrap_future(future)  # 中断 cancel 的是 await,底层 _run 继续
        return '成功打开并进入绝区零游戏' if result.success else f'打开游戏失败: {result.status}'
    return open_and_enter_game


def make_get_run_status(backend: ZzzBackendContext) -> Callable[[], RunStatusResult]:
    """构造 ``get_run_status`` tool(模块级,便于独立测试)。"""
    def get_run_status() -> RunStatusResult:
        """查当前/最近一次运行状态(无副作用)。

        运行中返当前节点/耗时/重试;非运行返结果/失败定位。
        """
        return backend.query_status()
    return get_run_status


def make_stop_run(backend: ZzzBackendContext) -> Callable[[], dict]:
    """构造 ``stop_run`` tool(模块级,便于独立测试)。"""
    def stop_run() -> dict:
        """发出停止信号,operation 在当前节点完成后退出(非强杀)。

        返回仅表信号已发出(过渡期 get_run_status 仍显示 running)。
        """
        return backend.stop()
    return stop_run


def create_mcp_server(backend: ZzzBackendContext, name: str = "zzz_od") -> FastMCP:
    """创建 MCP 服务器并注册 game 工具。

    通过闭包将 ``backend`` 注入到各工具函数中，使工具调用最终落到 backend 的
    game 切片方法（``check_window``/``capture``/``analyze``）；运行类操作
    （``open_and_enter_game``/``get_run_status``/``stop_run``）经模块级工厂
    构造后用 ``mcp.tool()(...)`` 注册。

    Args:
        backend: 已就绪的 ``ZzzBackendContext``，提供 game 切片能力。
        name: MCP 服务器名称，默认 ``zzz_od``。

    Returns:
        注册好工具的 ``FastMCP`` 实例。
    """
    mcp = FastMCP(name)

    @mcp.tool()
    def check_game_window() -> str:
        """检查绝区零游戏窗口状态。

        读取窗口标题、有效性、激活态、缩放比例及客户区矩形，格式化为可读字符串。

        Returns:
            窗口状态描述字符串；backend 抛错时返回 ``错误: <原因>``。
        """
        try:
            s = backend.check_window()
        except Exception as e:  # noqa: BLE001 工具层统一兜底，避免异常透传到 MCP 框架
            return f"错误: {e}"
        lines = [
            "游戏窗口状态:",
            f"  窗口标题: {s.win_title}",
            f"  窗口有效: {s.is_win_valid}",
            f"  窗口激活: {s.is_win_active}",
            f"  窗口缩放: {s.is_win_scale}",
        ]
        if s.x is not None:
            lines.append(f"  窗口位置: x={s.x}, y={s.y}, 宽={s.width}, 高={s.height}")
        return "\n".join(lines)

    @mcp.tool()
    def capture_game_screen() -> str:
        """捕获游戏画面并保存截图，返回截图绝对路径。

        Returns:
            截图文件的绝对路径；backend 抛错时返回 ``错误: <原因>``。
        """
        try:
            image = backend.capture()
            path = _save_screenshot(image)
        except Exception as e:  # noqa: BLE001 工具层统一兜底
            return f"错误: {e}"
        log.info(f"截图已保存到: {path}")
        return path

    @mcp.tool()
    def analyze_screen() -> AnalyzeScreenResult:
        """分析画面（截图 + OCR + 画面匹配），返回结构化结果。

        Returns:
            ``AnalyzeScreenResult``（成功标志、OCR 文本列表、画面匹配结果、错误描述）。
            决策优先看 ``screens``（精准命中 1 个 ``is_precise=True``；否则 top_n 个候选）；
            需要散落文本（未归类到任何 area 的 OCR 文本）再看 ``ocr_texts``。
        """
        try:
            return backend.analyze()
        except Exception as e:  # noqa: BLE001 工具层统一兜底
            return AnalyzeScreenResult(success=False, ocr_texts=[], error=str(e))

    @mcp.tool()
    def close_game() -> str:
        """关闭游戏(发关闭窗口信号,秒级)。

        controller 吞异常不返成功标志,故只表「信号已发」—— 用 check_game_window
        验证是否真关。backend 未就绪 / 窗口未就绪时返 ``错误: <原因>``。

        Returns:
            backend ``close_game`` 返回的文本;backend 抛错时返回 ``错误: <原因>``。
        """
        try:
            return backend.close_game()
        except Exception as e:  # noqa: BLE001 工具层兜底(BackendNotReadyError 等)
            return f"错误: {e}"

    mcp.tool()(make_open_and_enter_game(backend))
    mcp.tool()(make_get_run_status(backend))
    mcp.tool()(make_stop_run(backend))

    return mcp
