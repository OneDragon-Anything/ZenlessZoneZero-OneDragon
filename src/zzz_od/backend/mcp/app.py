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

tool 写法（annotations / Field / 返回 / docstring）遵循
``docs/develop/zzz/backend/mcp-implementation.md``。
"""

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from one_dragon.utils.log_utils import log
from zzz_od.backend.backend_context import ZzzBackendContext, _save_screenshot
from zzz_od.backend.mcp.prompts import (
    register_prompt_tools,
    register_prompts,
    render_instructions,
)
from zzz_od.backend.mcp.service_app import (
    make_describe_operation,
    make_get_predefined_teams,
    make_list_applications,
    make_list_operations,
    make_run_one_dragon,
    make_run_operation,
    make_run_standalone_app,
)
from zzz_od.backend.schemas import AnalyzeScreenResult, RunStatusResult, WindowStatus

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_base import OperationResult


def make_open_game(backend: ZzzBackendContext) -> Callable:
    """构造 ``open_game`` tool(模块级,便于独立测试)。

    enter=True(默认)跑 ``OpenAndEnterGame``(打开+自动登录,到大世界);
    enter=False 跑 ``OpenGame``(打开+等窗口就绪,停在打开游戏 ready 态,不登录)。
    其余 block/并发语义同原 ``open_and_enter_game``。
    """
    async def open_game(
        enter: Annotated[bool, Field(description="True=打开+自动登录到大世界;False=只打开停在 ready 态不登录")] = True,
        block: Annotated[bool, Field(description="True=阻塞到完成;False=立刻返回,用 get_run_status 查进度")] = True,
    ) -> dict | str:
        """打开游戏(可选自动登录)。长耗时,需交互式桌面。操作类。

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
        """查当前/最近一次运行状态(无副作用)。观察类。

        运行中返当前节点/耗时/重试;非运行返结果/失败定位。停止运行用 ``stop_run``。
        """
        return backend.query_status()
    return get_run_status


def make_stop_run(backend: ZzzBackendContext) -> Callable[[], dict]:
    """构造 ``stop_run`` tool(模块级,便于独立测试)。"""
    def stop_run() -> dict:
        """发出停止信号,operation 在当前节点完成后退出(非强杀)。操作类。

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
    mcp = FastMCP(name, instructions=render_instructions())

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="检查游戏窗口"))
    def check_game_window() -> WindowStatus | dict:
        """检查绝区零游戏窗口状态(只读,不改状态)。观察类。

        返回窗口标题、有效性、激活态、缩放比例及客户区矩形(与 HTTP ``/game/window`` 同构)。

        Returns:
            ``WindowStatus``(win_title / is_win_valid / is_win_active / is_win_scale /
            x / y / width / height;位置字段不可用时为 None);backend 抛错时返回
            ``{'error': <原因>}``。
        """
        try:
            return backend.check_window()
        except Exception as e:  # noqa: BLE001 工具层统一兜底，避免异常透传到 MCP 框架
            return {'error': str(e)}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="捕获游戏截图"))
    def capture_game_screen() -> str:
        """捕获游戏画面并保存截图，返回截图绝对路径。观察类。

        只截图不分析用本 tool;需 OCR / 画面匹配用 ``analyze_screen``。

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

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="分析游戏画面"))
    def analyze_screen(
        screenshot: Annotated[str | None, Field(description="截图来源:None=实时截当前画面(需游戏在线);传路径=读该图(无需游戏在线);纯名字=读 .debug/images/<名字>.png")] = None,
        save_image: Annotated[bool, Field(description="仅实时模式:把截图落盘并回传 screenshot_path 供 vision 复用;离线模式忽略")] = False,
    ) -> AnalyzeScreenResult:
        """分析画面(截图 + OCR + 画面匹配),返回结构化结果。观察类,不改游戏状态。

        只需截图标路径用 ``capture_game_screen``;本 tool 截图 + 分析。

        screenshot 省略 → 截当前游戏画面(需游戏在线),精准命中回写当前画面名;
        screenshot 传入 → 解析指定截图、**无需游戏在线**:绝对路径按路径读 / 纯名字到
        ``.debug/images/<名字>.png`` 读;**不回写**识别状态。用于离线校验/反哺 screen_info。

        save_image=True(**仅实时模式**)→ 把截图落盘并把路径放进 ``screenshot_path``
        返回,供 vision 复用(省掉另调 capture_game_screen)。离线模式忽略。

        Returns:
            ``AnalyzeScreenResult``(成功标志、OCR 文本列表、画面匹配结果、错误描述、
            screenshot_path、vision_hint)。
            决策优先看 ``screens``(精准命中 1 个 ``is_precise=True``;否则 top_n 个候选);
            需要散落文本(未归类到任何 area 的 OCR 文本)再看 ``ocr_texts``。
            ``vision_hint``(success 时):本结果仅含 OCR + 模板匹配的部分识别,不等同完整
            视觉理解;需要全面判断画面时配合视觉工具 / 多模态再看(能力边界提醒,非错误)。
        """
        try:
            return backend.analyze(screenshot, save_image)
        except Exception as e:  # noqa: BLE001 工具层统一兜底，避免异常透传到 MCP 框架
            return AnalyzeScreenResult(success=False, ocr_texts=[], screens=[], error=str(e))

    @mcp.tool(annotations=ToolAnnotations(title="增改画面区域"))  # 操作类:改 screen_info(写 yml + reload)
    def upsert_screen_area(
        screen_name: str, area_name: str,
        pc_rect: Annotated[list[int], Field(description="area 矩形 [x1,y1,x2,y2],1080p 游戏坐标;模板 bbox 建议每边 +10px")],
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

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, title="删除画面区域"))  # 操作类+不可逆:删 screen_info area
    def delete_screen_area(screen_name: str, area_name: str) -> dict:
        """按 area_name 删除指定 screen 的一个 area(写 yml + reload)。操作类,不可逆。

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

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, title="关闭游戏"))  # 操作类+破坏性:关游戏
    def close_game() -> str:
        """关闭游戏(发关闭窗口信号,秒级)。操作类。

        controller 吞异常不返成功标志,故只表「信号已发」—— 用 check_game_window
        验证是否真关。backend 未就绪 / 窗口未就绪时返 ``错误: <原因>``。

        Returns:
            backend ``close_game`` 返回的文本;backend 抛错时返回 ``错误: <原因>``。
        """
        try:
            return backend.close_game()
        except Exception as e:  # noqa: BLE001 工具层兜底(BackendNotReadyError 等)
            return f"错误: {e}"

    @mcp.tool(annotations=ToolAnnotations(title="点击游戏坐标"))  # 操作类:操作游戏点击(非破坏)
    def click_game(
        x: float, y: float,
        press_time: Annotated[float, Field(description="按住时长(秒);默认 0.1(游戏识别下限,0=极短按可能无效)")] = 0.1,
        pc_alt: Annotated[bool, Field(description="点击前是否按住 Alt 解锁光标;大世界等 pc_alt=true 画面必需,其余 False")] = False,
    ) -> dict:
        """点击游戏窗口内坐标(1080p 游戏空间,同 screen_info pc_rect 中心)。操作类。

        鼠标点击用本 tool;键盘按键用 ``key_tap``;鼠标拖拽用 ``drag``。

        坐标经控制器缩放到真实屏幕;不在窗口内则不点击(in_window=False)。需游戏窗口就绪。

        pc_alt=True 时点击前先按住 Alt 解锁光标 —— 大世界等 pc_alt=true 画面必需
        (绝区零锁光标,不按 Alt 点击落空)。判断依据:目标画面对应 screen_info
        的 ``pc_alt`` 字段;框架内部点击(跑 application)会自动带,经 MCP 手动点击
        pc_alt 画面时需显式传 True。其余画面保持 False。

        ⚠️ 操作后建议 sleep:底层 click 无内置等待,点 UI 常触发画面切换(菜单/弹窗/
        进画面),连续操作或 ``capture_game_screen`` 前建议 sleep ~1s 等动画(否则截过渡帧)。

        Returns:
            ``{success, x, y, in_window, pc_alt, error?}``;backend 抛错时 success=False + error。
        """
        try:
            return backend.click_game(x, y, press_time, pc_alt)
        except Exception as e:  # noqa: BLE001 工具层兜底
            return {'success': False, 'x': x, 'y': y, 'in_window': False, 'pc_alt': pc_alt, 'error': str(e)}

    @mcp.tool(annotations=ToolAnnotations(title="键盘按键"))  # 操作类:键盘输入(非破坏)
    def key_tap(
        key: Annotated[str, Field(description="框架键名:w/a/s/d 移动、f 交互、esc、space 等(沿用框架 btn_controller 约定)")],
        press_time: Annotated[float, Field(description="按住时长(秒);0=短按 tap,>0=长按(如移动长按 1-2s)")] = 0.0,
    ) -> dict:
        """键盘按键(press_time=0 短按,>0 长按)。操作类。

        键盘按键用本 tool;鼠标点击用 ``click_game``;拖拽用 ``drag``。

        覆盖框架 btn_controller 能发的键:移动 ``w``/``a``/``s``/``d``、交互 ``f``、
        ``esc``、``space`` 等(键名沿用框架约定)。press_time>0 长按(如移动长按 1-2s)。
        需游戏窗口就绪。

        ⚠️ 操作后建议 sleep(底层无内置等待):移动 wasd ~1s 等角色到位(不等就 interact
        可能失效,见 scratch_card issue #2405)、交互 ``f`` ~1-2s 进场景/对话、``esc``
        ~0.5s 开关菜单。连续操作前按需 sleep。

        Returns:
            ``{success, key, press_time, error?}``;backend 抛错时 success=False + error。
        """
        try:
            return backend.key_tap(key, press_time)
        except Exception as e:  # noqa: BLE001 工具层兜底
            return {'success': False, 'key': key, 'press_time': press_time, 'error': str(e)}

    @mcp.tool(annotations=ToolAnnotations(title="鼠标拖拽"))  # 操作类:鼠标拖拽(非破坏)
    def drag(
        x1: float, y1: float, x2: float, y2: float,
        duration: Annotated[float, Field(description="拖拽耗时(秒),默认 1.0")] = 1.0,
    ) -> dict:
        """鼠标按住拖拽((x1,y1)→(x2,y2),1080p 游戏坐标,同 screen_info pc_rect)。操作类。

        鼠标拖拽用本 tool;点击用 ``click_game``;按键用 ``key_tap``。

        覆盖刮刮卡刮开、八卦收集来回拖、咖啡拖动等。需游戏窗口就绪。

        ⚠️ 操作后建议 sleep:底层 drag 无内置等待,拖后画面变化(刮/滚),连续操作或
        capture 前建议 sleep ~0.5s。

        Returns:
            ``{success, x1, y1, x2, y2, duration, error?}``;backend 抛错时 success=False + error。
        """
        try:
            return backend.drag(x1, y1, x2, y2, duration)
        except Exception as e:  # noqa: BLE001 工具层兜底
            return {'success': False, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'duration': duration, 'error': str(e)}

    @mcp.tool(annotations=ToolAnnotations(title="输入文本"))  # 操作类:文本输入(非破坏)
    def input_text(
        text: Annotated[str, Field(description="要输入的文本(账号/密码/兑换码等)")],
        use_clipboard: Annotated[bool | None, Field(description="None=跟随 game_config.type_input_way;True=强制剪贴板;False=强制逐键")] = None,
    ) -> dict:
        """向当前焦点输入框输入文本(账号/密码等)。操作类。

        需先用 click_game 点击输入框聚焦。需游戏窗口就绪。

        Returns:
            ``{success, method, masked_text, error?}``;backend 抛错时 success=False + error。
        """
        try:
            return backend.input_text(text, use_clipboard)
        except Exception as e:  # noqa: BLE001 工具层兜底
            return {'success': False, 'method': None, 'masked_text': None, 'error': str(e)}

    # 运行类 / 查询类工厂 tool:annotations(含 title)在注册时传(函数定义在 service_app.py)
    mcp.tool(annotations=ToolAnnotations(title="打开游戏"))(make_open_game(backend))
    mcp.tool(annotations=ToolAnnotations(title="运行一条龙"))(make_run_one_dragon(backend))
    mcp.tool(annotations=ToolAnnotations(title="运行独立应用"))(make_run_standalone_app(backend))
    mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="列出可运行应用"))(make_list_applications(backend))
    mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="读取预备编队列表"))(make_get_predefined_teams(backend))
    mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="查询运行状态"))(make_get_run_status(backend))
    mcp.tool(annotations=ToolAnnotations(title="停止运行"))(make_stop_run(backend))
    mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="列出可运行 operation"))(make_list_operations(backend))
    mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, title="查看 operation 参数"))(make_describe_operation(backend))
    mcp.tool(annotations=ToolAnnotations(title="运行 operation"))(make_run_operation(backend))
    register_prompts(mcp)
    register_prompt_tools(mcp)

    return mcp
