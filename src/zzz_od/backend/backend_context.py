"""后端服务层：传输无关地包装 ZContext，提供感知/操作方法。

本模块是后端 game 切片的地基：
- ``ZzzBackendContext`` 持有 ``ZContext``，管理其生命周期，并对外暴露与
  传输协议（HTTP/IPC 等）无关的感知/操作方法。
- ``BackendNotReadyError`` 在前置校验失败（ZContext 尚未就绪）时抛出。

game 切片方法（``check_window``/``capture``/``analyze``/``enter_game``）从
``ZContext`` 的控制器、OCR 服务、运行上下文中读取数据，并以 ``zzz_od.backend.schemas``
中的传输无关结构返回。
"""

import asyncio
from typing import TYPE_CHECKING

from zzz_od.backend.schemas import AnalyzeScreenResult, OcrText, WindowStatus
from zzz_od.context.zzz_context import ZContext

if TYPE_CHECKING:
    from cv2.typing import MatLike


class BackendNotReadyError(Exception):
    """后端未就绪。

    当 ``ZContext`` 尚未完成初始化，或控制器/游戏窗口缺失时抛出，
    用于在调用 game 切片方法前做统一的前置校验。
    """


class ZzzBackendContext:
    """后端 context：持有 ``ZContext``，管理生命周期，暴露传输无关方法。

    设计要点：
        - 生命周期方法（``start``/``shutdown``）通过 ``asyncio.to_thread``
          在线程池中调用 ``ZContext`` 的同步初始化/清理逻辑，避免阻塞事件循环。
        - ``ctx`` 属性仅供同进程内部使用，不应通过适配器对外暴露原始 context。
        - 任何 game 切片方法在执行前应先调用 ``_ensure_ready`` 校验。
    """

    def __init__(self, ctx: ZContext) -> None:
        """初始化后端 context。

        Args:
            ctx: 被包装的 ``ZContext`` 实例，由调用方负责构造并注入。
        """
        self._ctx: ZContext = ctx

    @property
    def ctx(self) -> ZContext:
        """底层 ``ZContext``（仅同进程内部使用，不对外通过适配器暴露）。"""
        return self._ctx

    def _ensure_ready(self) -> None:
        """前置校验：确认 ``ZContext`` 已完成初始化、可运行应用。

        Raises:
            BackendNotReadyError: 当 ``ctx.ready_for_application`` 为 False 时抛出。
        """
        if not self._ctx.ready_for_application:
            raise BackendNotReadyError('ZContext 未就绪（ready_for_application=False）')

    def check_window(self) -> WindowStatus:
        """检查游戏窗口状态。

        读取控制器上当前的游戏窗口信息，封装为传输无关的 ``WindowStatus`` 返回。
        窗口矩形不可用时，坐标/尺寸字段为 None。

        Returns:
            游戏窗口状态（标题、有效性、激活态、缩放、客户区矩形）。

        Raises:
            BackendNotReadyError: ``ZContext`` 未就绪，或控制器/游戏窗口未初始化时抛出。
        """
        self._ensure_ready()
        controller = self._ctx.controller
        if controller is None or controller.game_win is None:
            raise BackendNotReadyError('控制器或游戏窗口未初始化')
        game_win = controller.game_win
        rect = game_win.win_rect
        return WindowStatus(
            win_title=game_win.win_title,
            is_win_valid=game_win.is_win_valid,
            is_win_active=game_win.is_win_active,
            is_win_scale=game_win.is_win_scale,
            x=rect.x1 if rect is not None else None,
            y=rect.y1 if rect is not None else None,
            width=rect.width if rect is not None else None,
            height=rect.height if rect is not None else None,
        )

    def capture(self) -> 'MatLike':
        """截取游戏当前画面。

        通过控制器对游戏窗口进行截图，返回 RGB ``ndarray``。

        Returns:
            截图图像（RGB ``MatLike``）。

        Raises:
            BackendNotReadyError: ``ZContext`` 未就绪、游戏窗口未就绪或截图返回 None 时抛出。
        """
        self._ensure_ready()
        controller = self._ctx.controller
        if controller is None or not controller.is_game_window_ready:
            raise BackendNotReadyError('游戏窗口未就绪')
        image = controller.get_screenshot(independent=False)
        if image is None:
            raise BackendNotReadyError('截图返回 None')
        return image

    def analyze(self) -> AnalyzeScreenResult:
        """分析游戏画面：截图后执行 OCR。

        截图失败或游戏窗口未就绪时返回失败结果（``success=False``），
        成功时将 OCR 识别结果映射为 ``OcrText`` 列表返回。

        Returns:
            分析结果：成功标志、OCR 文本列表、失败时的错误描述。
        """
        self._ensure_ready()
        controller = self._ctx.controller
        if controller is None or not controller.is_game_window_ready:
            return AnalyzeScreenResult(success=False, ocr_texts=[], error='游戏窗口未就绪')
        image = controller.get_screenshot(independent=False)
        if image is None:
            return AnalyzeScreenResult(success=False, ocr_texts=[], error='截图失败')
        ocr_result_list = self._ctx.ocr_service.get_ocr_result_list(image=image)
        ocr_texts = [
            OcrText(
                text=r.data,
                x=int(r.x),
                y=int(r.y),
                width=int(r.w),
                height=int(r.h),
            )
            for r in ocr_result_list
        ]
        return AnalyzeScreenResult(success=True, ocr_texts=ocr_texts, error=None)

    def enter_game(self) -> str:
        """打开并进入游戏。

        通过 ``OpenAndEnterGame`` 操作打开并进入绝区零游戏。这是一个长阻塞流程，
        需要交互式桌面会话。调用前会先启动运行上下文，结束后无论成功与否都会停止运行上下文。

        Returns:
            执行结果描述字符串：成功时包含「成功」，失败时附带操作状态。

        Raises:
            BackendNotReadyError: ``ZContext`` 未就绪，或运行上下文启动失败时抛出。
        """
        self._ensure_ready()
        from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame

        run_context = self._ctx.run_context
        if not run_context.start_running():
            raise BackendNotReadyError('无法启动运行上下文')
        try:
            run_context.current_instance_idx = self._ctx.current_instance_idx
            op = OpenAndEnterGame(self._ctx)
            result = op.execute()
            if result.success:
                return '成功打开并进入绝区零游戏'
            return f'打开游戏失败: {result.status}'
        finally:
            run_context.stop_running()

    async def start(self) -> None:
        """启动服务：在线程池中初始化 ``ZContext``，不阻塞事件循环。

        ``ZContext.init()`` 是同步且可能较重的初始化流程（含 OCR/onnx 模型加载、
        控制器构建等）。通过 ``asyncio.to_thread`` 将其放到默认线程池执行，
        保证事件循环可继续调度其它协程。

        注意：
            ``ctx.init_async()`` 返回 None（fire-and-forget），不可 await；
            要等待初始化真正完成，必须使用 ``asyncio.to_thread(ctx.init)``。
        """
        await asyncio.to_thread(self._ctx.init)

    async def shutdown(self) -> None:
        """关闭服务：在线程池中释放 ``ZContext`` 持有的资源。

        ``ZContext.after_app_shutdown()`` 是同步的清理流程（遥测、战斗上下文、
        框架服务等），同样通过 ``asyncio.to_thread`` 避免阻塞事件循环。
        """
        await asyncio.to_thread(self._ctx.after_app_shutdown)
