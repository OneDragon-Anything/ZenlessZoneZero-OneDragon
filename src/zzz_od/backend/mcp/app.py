"""MCP 适配器：把 ``ZzzBackendContext`` 以 MCP tool 的形式对外暴露。

本模块在后端 game 切片（``ZzzBackendContext``）之上架设一层传输适配：
- ``create_mcp_server`` 创建一个 ``FastMCP`` 实例，并通过闭包将 backend 注入到
  工具函数中，使工具调用最终落到 backend 的 game 切片方法上。
- 工具返回值尽量保持「可直接读」的字符串或传输无关结构，便于上层（CLI/Agent）消费。

注意：
    - 同步工具（check/capture/analyze）直接调用 backend 的同步方法；
    - ``open_game`` 为异步长耗时操作，基于 ``backend.start_run`` 适配，
      ``block=True`` 阻塞到完成、``block=False`` 立刻返回。
    - 运行类 tool 工厂（``make_open_game`` 等）为模块级函数，
      只调 backend 公开方法，不戳 run_slot 私有，便于独立测试。
"""

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from one_dragon.utils.log_utils import log
from zzz_od.backend.backend_context import ZzzBackendContext, _save_screenshot
from zzz_od.backend.mcp.prompts import register_prompt_tools, register_prompts
from zzz_od.backend.mcp.service_app import (
    make_describe_operation,
    make_list_applications,
    make_list_operations,
    make_run_one_dragon,
    make_run_operation,
    make_run_standalone_app,
)
from zzz_od.backend.schemas import AnalyzeScreenResult, RunStatusResult

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_base import OperationResult


def make_open_game(backend: ZzzBackendContext) -> Callable:
    """构造 ``open_game`` tool(模块级,便于独立测试)。

    enter=True(默认)跑 ``OpenAndEnterGame``(打开+自动登录,到大世界);
    enter=False 跑 ``OpenGame``(打开+等窗口就绪,停在打开游戏 ready 态,不登录)。
    其余 block/并发语义同原 ``open_and_enter_game``。
    """
    async def open_game(enter: bool = True, block: bool = True) -> dict | str:
        """打开游戏(可选自动登录)。长耗时,需交互式桌面。

        enter=True(默认)→ 打开 + 自动登录(= 原 open_and_enter_game,到大世界);
        enter=False → 只打开 + 等窗口就绪,停在「打开游戏」ready 态(不登录),
        供调用方分步驱动登录流程。
        block=True(默认)阻塞到完成;block=False 立刻返回,用 get_run_status 查进度。
        副作用:操作游戏(启动 exe / 可能登录);单跑道,已有运行时返回错误(含 source + 提示)。
        """
        from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame
        from zzz_od.operation.enter_game.open_game import OpenGame
        op_factory = (lambda ctx: OpenGame(ctx)) if not enter else (lambda ctx: OpenAndEnterGame(ctx))
        ok, future = backend.start_run('mcp', op_factory)
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
        if enter:
            return '成功打开并进入绝区零游戏' if result.success else f'打开游戏失败: {result.status}'
        return '成功打开游戏(未登录)' if result.success else f'打开游戏失败: {result.status}'
    return open_game


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
    """创建 MCP 服务器并注册 game 工具与 prompt。

    通过闭包将 ``backend`` 注入到各工具函数中，使工具调用最终落到 backend 的
    game 切片方法（``check_window``/``capture``/``analyze``）；运行类操作
    （``open_game``/``get_run_status``/``stop_run``）经模块级工厂
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
    def analyze_screen(screenshot: str | None = None, save_image: bool = False) -> AnalyzeScreenResult:
        """分析画面(截图 + OCR + 画面匹配),返回结构化结果。观察类,不改游戏状态。

        screenshot 省略 → 截当前游戏画面(需游戏在线),精准命中回写当前画面名;
        screenshot 传入 → 解析指定截图、**无需游戏在线**:绝对路径按路径读 / 纯名字到
        ``.debug/images/<名字>.png`` 读;**不回写**识别状态。用于离线校验/反哺 screen_info。

        save_image=True(**仅实时模式**)→ 把截图落盘并把路径放进 ``screenshot_path``
        返回,供 vision 复用(省掉另调 capture_game_screen)。离线模式忽略。

        Returns:
            ``AnalyzeScreenResult``(成功标志、OCR 文本列表、画面匹配结果、错误描述、
            screenshot_path)。
            决策优先看 ``screens``(精准命中 1 个 ``is_precise=True``;否则 top_n 个候选);
            需要散落文本(未归类到任何 area 的 OCR 文本)再看 ``ocr_texts``。
        """
        try:
            return backend.analyze(screenshot, save_image)
        except Exception as e:  # noqa: BLE001 工具层统一兜底，避免异常透传到 MCP 框架
            return AnalyzeScreenResult(success=False, ocr_texts=[], screens=[], error=str(e))

    @mcp.tool()
    def upsert_screen_area(
        screen_name: str, area_name: str, pc_rect: list[int],
        text: str = '', lcs_percent: float = 0.5,
        template_sub_dir: str = '', template_id: str = '', template_match_threshold: float = 0.7,
        color_range: list[list[int]] | None = None, goto_list: list[str] | None = None,
        id_mark: bool = False, gamepad_key: str | None = None,
    ) -> dict:
        """按 area_name 在指定 screen 插入或更新一个 area(写 yml + reload)。操作类,改 screen_info。

        area_name 存在则整体更新,不存在则追加。校验:screen 存在、area_name 非空、pc_rect 合法、
        模板引用存在(template_id 非空时)。写回 yml 并 reload,下次 analyze_screen 即生效。无需游戏在线。

        Returns:
            dict: ``{success, screen_name, area_name, action(inserted/updated), area_count, error}``。
        """
        try:
            return backend.upsert_screen_area(
                screen_name, area_name, pc_rect, text, lcs_percent,
                template_sub_dir, template_id, template_match_threshold,
                color_range, goto_list, id_mark, gamepad_key,
            )
        except Exception as e:  # noqa: BLE001 工具层统一兜底
            return {'success': False, 'screen_name': screen_name, 'area_name': area_name,
                    'action': None, 'area_count': None, 'error': str(e)}

    @mcp.tool()
    def delete_screen_area(screen_name: str, area_name: str) -> dict:
        """按 area_name 删除指定 screen 的一个 area(写 yml + reload)。操作类。

        screen_name + area_name 定位;area 不存在则 success=False。
        写回 yml 并 reload,下次 analyze_screen 即生效。

        Returns:
            dict: ``{success, screen_name, area_name, action(deleted), area_count, error}``。
        """
        try:
            return backend.delete_screen_area(screen_name, area_name)
        except Exception as e:  # noqa: BLE001 工具层统一兜底
            return {'success': False, 'screen_name': screen_name, 'area_name': area_name,
                    'action': None, 'area_count': None, 'error': str(e)}

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

    @mcp.tool()
    def click_game(x: float, y: float, press_time: float = 0.0) -> dict:
        """点击游戏窗口内坐标(1080p 游戏空间,同 screen_info pc_rect 中心)。操作类。

        坐标经控制器缩放到真实屏幕;不在窗口内则不点击(in_window=False)。需游戏窗口就绪。

        Returns:
            ``{success, x, y, in_window, error?}``;backend 抛错时 success=False + error。
        """
        try:
            return backend.click_game(x, y, press_time)
        except Exception as e:  # noqa: BLE001 工具层兜底
            return {'success': False, 'x': x, 'y': y, 'in_window': False, 'error': str(e)}

    @mcp.tool()
    def input_text(text: str, use_clipboard: bool | None = None) -> dict:
        """向当前焦点输入框输入文本(账号/密码等)。操作类。

        use_clipboard=None 跟随 game_config.type_input_way;True/False 强制剪贴板/逐键。
        需先用 click_game 点击输入框聚焦。需游戏窗口就绪。

        Returns:
            ``{success, method, masked_text, error?}``;backend 抛错时 success=False + error。
        """
        try:
            return backend.input_text(text, use_clipboard)
        except Exception as e:  # noqa: BLE001 工具层兜底
            return {'success': False, 'method': None, 'masked_text': None, 'error': str(e)}

    mcp.tool()(make_open_game(backend))
    mcp.tool()(make_run_one_dragon(backend))
    mcp.tool()(make_run_standalone_app(backend))
    mcp.tool()(make_list_applications(backend))
    mcp.tool()(make_get_run_status(backend))
    mcp.tool()(make_stop_run(backend))
    mcp.tool()(make_list_operations(backend))
    mcp.tool()(make_describe_operation(backend))
    mcp.tool()(make_run_operation(backend))
    register_prompts(mcp)
    register_prompt_tools(mcp)

    return mcp
