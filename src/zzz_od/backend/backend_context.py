"""后端服务层：传输无关地包装 ZContext，提供感知/操作方法。

本模块是后端 game 切片的地基：
- ``ZzzBackendContext`` 持有 ``ZContext``，管理其生命周期，并对外暴露与
  传输协议（HTTP/IPC 等）无关的感知/操作方法。
- ``BackendNotReadyError`` 在前置校验失败（ZContext 尚未就绪）时抛出。

game 切片方法（``check_window``/``capture``/``analyze``）从
``ZContext`` 的控制器、OCR 服务、运行上下文中读取数据，并以 ``zzz_od.backend.schemas``
中的传输无关结构返回。运行类操作通过 ``start_run``/``query_status``/``stop``
委托给 ``run_slot``(RunSlot)。
"""

import asyncio
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.screen.screen_match import find_screen_matches
from zzz_od.backend.schemas import (
    AnalyzeScreenResult,
    OcrText,
    RunStatusResult,
    WindowStatus,
)
from zzz_od.context.zzz_context import ZContext

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.operation.operation import Operation


def _iso(ts: float | None) -> str | None:
    """epoch 秒 → ISO 字符串(None 透传)。"""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts).isoformat()


class RunState(str, Enum):
    """RunSlot 状态。

    IDLE:从未运行;RUNNING:operation 活(含 stop 后退出中的间隙,统一报 RUNNING);
    SUCCESS/FAILED/STOPPED:终态(固化)。无 PAUSED(当前不可达)、无 STOPPING(框架无此态)。
    """

    IDLE = 'idle'
    RUNNING = 'running'
    SUCCESS = 'success'
    FAILED = 'failed'
    STOPPED = 'stopped'


class RunSlot:
    """单跑道运行槽:MCP/HTTP 共享,固化终态,运行中读 operation 实例。

    状态判据用固化字段 terminal_state(单一事实源),不读 run_context 推中间态。
    详见 docs/superpowers/specs/2026-07-02-mcp-async-operation-design.md。
    """

    def __init__(self, ctx: 'ZContext') -> None:
        self._ctx: ZContext = ctx
        self._lock: threading.Lock = threading.Lock()
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='zzz_backend_run')
        self.source: str | None = None
        self.app: str | None = None
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.terminal_state: RunState | None = None
        self.last_status: str | None = None
        self.failed_node: str | None = None
        self.future: Future | None = None
        self.current_op: Operation | None = None

    def _start_run(self, source: str, op_factory: 'Callable[[ZContext], Operation]') -> tuple[bool, Future | None]:
        """触发运行。单跑道:已在跑则拒绝。

        Returns:
            (ok, future):ok=False 表示已有运行在进行(future=None);ok=True 表示已启动。
        """
        with self._lock:
            if self.future is not None and not self.future.done():
                return False, None
            self.terminal_state = None
            self.last_status = None
            self.failed_node = None
            self.finished_at = None
            self.app = None
            self.source = source
            self.started_at = time.time()
            self.future = self._executor.submit(self._run, op_factory)
            return True, self.future

    def _run(self, op_factory: 'Callable[[ZContext], Operation]') -> OperationResult | None:
        """后台线程:启动 run_context → 跑 operation → finally 固化终态 + stop_running。

        并发(已在跑)已在 _start_run 拦截;此处 start_running 返回 False 只可能是初始化失败。
        终态判据:OperationResult.status == '人工结束' → STOPPED(框架唯一 stop 标记)。
        返回 OperationResult(future 解析值)供 block=True 的适配器 await 后取结果。
        """
        run_context = self._ctx.run_context
        op: Operation | None = None
        result: OperationResult | None = None
        terminal: RunState = RunState.FAILED
        failed_node: str | None = None   # 局部累积,finally 锁内固化(避免锁外写固化字段)
        try:
            if not run_context.start_running():
                failed_node = 'start_running 初始化失败'
                result = OperationResult(success=False, status='start_running 初始化失败')
            else:
                run_context.current_instance_idx = self._ctx.current_instance_idx
                op = op_factory(self._ctx)
                with self._lock:
                    self.current_op = op
                    self.app = op.__class__.__name__
                result = op.execute()
                if result.success:
                    terminal = RunState.SUCCESS
                elif result.status == '人工结束':
                    terminal = RunState.STOPPED
                else:
                    terminal = RunState.FAILED
                    failed_node = op._current_node.cn if op._current_node is not None else None
        except Exception as e:  # noqa: BLE001 兜底:execute 抛异常也固化,避免卡 terminal_state=None
            terminal = RunState.FAILED
            if op is not None and op._current_node is not None:
                failed_node = op._current_node.cn
            else:
                failed_node = f'异常: {e}'
            result = OperationResult(success=False, status='执行异常')
        finally:
            with self._lock:
                self.terminal_state = terminal
                self.last_status = result.status if result is not None else '执行异常'
                self.failed_node = failed_node
                self.finished_at = time.time()
                self.current_op = None
            run_context.stop_running()
        return result

    def _query_status(self) -> RunStatusResult:
        """查询运行状态。判据用固化 terminal_state(单一事实源),不读 run_context。

        终态:返固化 terminal_state + last_status/failed_node。
        运行中(started_at 非 None 且 terminal_state None):统一 RUNNING,读 current_op 的 current_node/retry。
        空闲(从未运行,started_at None):返 idle。
        """
        with self._lock:
            if self.terminal_state is not None:
                duration = (self.finished_at - self.started_at) if (self.finished_at and self.started_at) else None
                return RunStatusResult(
                    state=self.terminal_state.value,
                    source=self.source, app=self.app,
                    started_at=_iso(self.started_at), duration_seconds=duration,
                    last_status=self.last_status, failed_node=self.failed_node,
                )
            source = self.source
            app = self.app
            started_at = self.started_at
            op = self.current_op
            if started_at is None:
                return RunStatusResult(state=RunState.IDLE.value, source=source)
        current_node = op._current_node.cn if op is not None and op._current_node is not None else None
        retry_count = op.node_retry_times if op is not None else None
        duration = (time.time() - started_at) if started_at else None
        return RunStatusResult(
            state=RunState.RUNNING.value,
            source=source, app=app,
            started_at=_iso(started_at), duration_seconds=duration,
            current_node=current_node, retry_count=retry_count,
        )

    def _stop(self) -> tuple[bool, str | None]:
        """发出停止信号(run_context.stop_running 直接设 STOP,非阻塞)。

        operation 实际退出有过渡期(下一轮才退),期间 _query_status 仍报 running。

        Returns:
            (stopped, source):无运行 → (False, None);否则 (True, 被停运行的触发方)。
        """
        with self._lock:
            if self.future is None or self.future.done():
                return False, None
            source = self.source
        self._ctx.run_context.stop_running()
        return True, source


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
        self.run_slot: RunSlot = RunSlot(ctx)

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
        """分析游戏画面:截图 + 全图 OCR + 画面匹配(精准/模糊)。

        精准命中(``screens[0].is_precise=True``)后回写
        ``ctx.screen_loader.update_current_screen_name``,为下次 BFS 提供起点;
        模糊 / 异常不回写。

        对外无副作用(MCP tool annotations readOnly —— 回写的是 ctx 内存识别状态,
        非外部资源)。Python GIL 下并发回写容忍(见 spec §2.3,无内存撕裂,
        逻辑竞态由 BFS 全量兜底吸收)。

        Returns:
            分析结果:成功标志、OCR 文本列表、画面匹配列表、错误描述。
        """
        self._ensure_ready()
        controller = self._ctx.controller
        if controller is None or not controller.is_game_window_ready:
            return AnalyzeScreenResult(success=False, ocr_texts=[], screens=[], error='游戏窗口未就绪')
        image = controller.get_screenshot(independent=False)
        if image is None:
            return AnalyzeScreenResult(success=False, ocr_texts=[], screens=[], error='截图失败')
        try:
            ocr_result_list = self._ctx.ocr_service.get_ocr_result_list(image=image)
            ocr_texts = [
                OcrText(text=r.data, x=int(r.x), y=int(r.y), width=int(r.w), height=int(r.h))
                for r in ocr_result_list
            ]
            screens = find_screen_matches(self._ctx, image)
            if screens and screens[0].is_precise:
                self._ctx.screen_loader.update_current_screen_name(screens[0].screen_name)
            return AnalyzeScreenResult(success=True, ocr_texts=ocr_texts, screens=screens, error=None)
        except Exception as e:  # noqa: BLE001 OCR/匹配异常兜底:不回写,返失败(对齐 spec §2.3;OCR 也纳入兜底更稳,调用方统一见 error 字段)
            return AnalyzeScreenResult(success=False, ocr_texts=[], screens=[], error=str(e))

    def close_game(self) -> str:
        """关闭游戏(发关闭窗口信号,秒级,不走 RunSlot)。

        controller.close_game() 内部 try/except 吞异常(log)、不返成功标志,
        故无法区分关成功/失败 —— 返「已发送关闭信号」,用 check_game_window 验证。

        Returns:
            '已发送关闭游戏信号,可用 check_game_window 验证'。

        Raises:
            BackendNotReadyError: ZContext 未就绪或游戏窗口未就绪时抛。
        """
        self._ensure_ready()
        controller = self._ctx.controller
        if controller is None or not controller.is_game_window_ready:
            raise BackendNotReadyError('游戏窗口未就绪')
        controller.close_game()
        return '已发送关闭游戏信号,可用 check_game_window 验证'

    def start_run(self, source: str, op_factory: 'Callable[[ZContext], Operation]') -> tuple[bool, Future | None]:
        """触发运行(供 MCP/HTTP 适配器调用,返回 future 供 block=True 时 await)。

        单跑道委托 ``run_slot._start_run``:已有运行在进行时返回 ``ok=False``，
        适配器据此返回并发拒绝；其余由 RunSlot 在后台线程内执行 operation。

        Args:
            source: 触发方标识，如 ``"mcp"``/``"http"``。
            op_factory: operation 构造器，由适配器提供。

        Returns:
            ``(ok, future)``：``ok=False`` 表示已有运行在进行(``future=None``)；
            ``ok=True`` 表示已启动，``future`` 可供阻塞 await 取结果。
        """
        return self.run_slot._start_run(source, op_factory)

    def query_status(self) -> RunStatusResult:
        """查询运行状态(委托 ``run_slot._query_status``)。

        Returns:
            当前运行状态的传输无关结构。
        """
        return self.run_slot._query_status()

    def stop(self) -> dict:
        """停止当前运行(委托 ``run_slot._stop``)。

        Returns:
            ``{"stopped": True, "source": <触发方>}`` 成功发出停止信号；
            ``{"stopped": False, "error": "当前无运行"}`` 无运行可停。
        """
        stopped, source = self.run_slot._stop()
        if not stopped:
            return {'stopped': False, 'error': '当前无运行'}
        return {'stopped': True, 'source': source}

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
