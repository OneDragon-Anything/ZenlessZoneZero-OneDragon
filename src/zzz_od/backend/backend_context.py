"""后端服务层：传输无关地包装 ZContext，提供感知/操作方法。

本模块是后端 game 切片的地基：
- ``ZzzBackendContext`` 持有 ``ZContext``，管理其生命周期，并对外暴露与
  传输协议（HTTP/IPC 等）无关的感知/操作方法。
- ``BackendNotReadyError`` 在前置校验失败（ZContext 尚未就绪）时抛出。

game 切片方法（``check_window``/``capture``/``analyze``）从
``ZContext`` 的控制器、OCR 服务、运行上下文中读取数据，并以 ``zzz_od.backend.schemas``
中的传输无关结构返回。运行类操作（``start_run``/``run_one_dragon``/
``run_standalone_app``/``query_status``/``stop``）统一委托给单个 ``RunSlot``，
槽内按 app / op 路径分派（详见 ``RunSlot``）。
"""

import asyncio
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from one_dragon.base.config.basic_game_config import TypeInputWay
from one_dragon.base.controller.pc_clipboard import PcClipboard
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.application.application_run_context import (
    RunFinishReason,
)
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_match import find_screen_matches
from one_dragon.utils import cv2_utils, debug_utils, os_utils
from one_dragon.utils.log_utils import mask_text
from zzz_od.application.shiyu_defense import shiyu_defense_const
from zzz_od.backend.schemas import (
    AnalyzeScreenResult,
    ApplicationInfo,
    ApplicationListResult,
    OcrText,
    PredefinedTeamItem,
    PredefinedTeamListResult,
    RunStatusResult,
    WindowStatus,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent, AgentEnum, DmgTypeEnum

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.operation.operation import Operation
    from zzz_od.application.shiyu_defense.shiyu_defense_config import ShiyuDefenseConfig
    from zzz_od.config.team_config import PredefinedTeamInfo


# agent_id(主 id)→ Agent 映射;team_config 存的是 agent_id 主 id,用于查 dmg_type 推导弱点。
_AGENT_MAP: dict[str, Agent] = {e.value.agent_id: e.value for e in AgentEnum}


# analyze_screen 返回的能力边界提示:本结果仅含 OCR + 模板匹配的部分识别,
# 提醒调用方(智能体)需要全面判断画面时,补一步视觉工具 / 多模态再看。
# 见 docs/develop/zzz/backend/design-principles.md P6/P13。
_VISION_HINT = (
    '本结果仅包含 OCR 识别的文字与模板匹配的命中项,是画面的部分识别结果,'
    '不等同于对画面的完整视觉理解。需要全面判断画面时,请用视觉工具或多模态大模型再看一遍该画面。'
)


def _iso(ts: float | None) -> str | None:
    """epoch 秒 → ISO 字符串(None 透传)。"""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts).isoformat()


def _validate_pc_rect(pc_rect: list[int]) -> str | None:
    """校验 pc_rect=[x1,y1,x2,y2];合法返 None,否则返错误描述。"""
    if (not isinstance(pc_rect, list) or len(pc_rect) != 4
            or not all(isinstance(v, int) for v in pc_rect)):
        return f'pc_rect 非法(需 4 个整数): {pc_rect}'
    x1, y1, x2, y2 = pc_rect
    if not (0 <= x1 < x2 <= 1920 and 0 <= y1 < y2 <= 1080):
        return f'pc_rect 越界或非正(需 1920×1080 内、x2>x1、y2>y1): {pc_rect}'
    return None


def _area_result(success: bool, screen_name: str, area_name: str, action: str | None,
                 error: str | None = None, count: int | None = None) -> dict:
    """构造 area CRUD 的统一返回 dict。"""
    return {
        'success': success,
        'screen_name': screen_name,
        'area_name': area_name,
        'action': action,
        'area_count': count,
        'error': error,
    }


class RunState(str, Enum):
    """运行槽状态。

    IDLE:从未运行;RUNNING:operation 活(含 stop 后退出中的间隙,统一报 RUNNING);
    SUCCESS/FAILED/STOPPED:终态(固化)。无 PAUSED(当前不可达)、无 STOPPING(框架无此态)。
    """

    IDLE = 'idle'
    RUNNING = 'running'
    SUCCESS = 'success'
    FAILED = 'failed'
    STOPPED = 'stopped'


class RunType(str, Enum):
    """运行单元类型:app 路径委托 run_application,op 路径槽自管生命周期。"""

    APPLICATION = 'application'
    OPERATION = 'operation'


class RunSlot:
    """单跑道运行槽:MCP/HTTP 共享,固化终态,运行中读 operation 实例。

    状态判据用固化字段 terminal_state(单一事实源),不读 run_context 推中间态。
    详见 docs/superpowers/specs/2026-07-02-mcp-async-operation-design.md。
    """

    def __init__(self, ctx: 'ZContext', thread_name_prefix: str = 'zzz_backend_run') -> None:
        self._ctx: ZContext = ctx
        self._lock: threading.Lock = threading.Lock()
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=thread_name_prefix)
        self.source: str | None = None
        self.op_id: str | None = None          # 唯一标识(定位用):app 路径=app_id、op 路径=display_name 或类名
        self.run_type: RunType | None = None   # APPLICATION / OPERATION
        self.app: str | None = None            # 展示名(_run 内固化):op 路径=op.op_name、app 路径=get_application_name
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.terminal_state: RunState | None = None
        self.last_status: str | None = None
        self.failed_node: str | None = None
        self.future: Future | None = None
        self.current_op: Operation | None = None

    def is_running(self) -> bool:
        """当前槽是否有未完成的运行。"""
        with self._lock:
            return self.future is not None and not self.future.done()

    def has_history(self) -> bool:
        """当前槽是否有可查询的历史运行。"""
        with self._lock:
            return self.started_at is not None

    def _start(
        self,
        source: str,
        op_factory: 'Callable[[ZContext], Operation] | None' = None,
        app_id: str | None = None,
        instance_idx: int | None = None,
        group_id: str | None = None,
        display_name: str | None = None,
        refresh_config: 'Callable[[], None] | None' = None,
    ) -> tuple[bool, Future | None]:
        """触发运行(单跑道)。op_factory 与 app_id 二选一,互斥校验。

        - op 路径(op_factory):槽自管 start_running/execute/stop_running(open_game / 自定义 op)。
        - app 路径(app_id):委托 run_application(复用 GUI/CLI 共享入口)。

        check 与 submit 在同一把锁内原子,消除跨槽 check-then-act 竞态。

        Args:
            source: 触发方标识(如 ``"mcp"``/``"http"``)。
            op_factory: operation 构造器(op 路径,与 app_id 互斥)。
            app_id: 应用 id(app 路径,与 op_factory 互斥)。
            instance_idx: 账号实例下标;op 路径 None 时取 ctx.current_instance_idx。
            group_id: 应用组 id(app 路径)。
            display_name: op 路径定位标识(如 op_id);None 时 _run 内 fallback 类名。
            refresh_config: 配置刷新钩子(app 路径在 run_application 前、_start 已赢锁后调用)。

        Returns:
            (ok, future):ok=False 表示已有运行在进行(future=None);ok=True 表示已启动。

        Raises:
            ValueError: op_factory 与 app_id 同时传或同时缺省。
        """
        if (op_factory is None) == (app_id is None):
            raise ValueError('op_factory 与 app_id 必须二选一')
        with self._lock:
            if self.future is not None and not self.future.done():
                return False, None                         # 单跑道:已在跑就拒(拒绝路径不刷新配置)
            self.terminal_state = None
            self.last_status = None
            self.failed_node = None
            self.finished_at = None
            self.op_id = app_id or display_name            # app 路径=app_id;op 路径=display_name,未传则 _run 内 fallback 类名
            self.run_type = RunType.APPLICATION if app_id is not None else RunType.OPERATION
            self.app = None                                # 展示名待 _run 填
            self.source = source
            self.started_at = time.time()
            self.future = self._executor.submit(
                self._run, source, op_factory, app_id, instance_idx, group_id, refresh_config,
            )
            return True, self.future

    def _run(
        self,
        source: str,
        op_factory: 'Callable[[ZContext], Operation] | None',
        app_id: str | None,
        instance_idx: int | None,
        group_id: str | None,
        refresh_config: 'Callable[[], None] | None',
    ) -> OperationResult | None:
        """后台线程:按 app / op 分派执行,顶层 try/except/finally 固化终态。

        - app 路径:refresh_config → 委托 run_application → 读 last_application_result。
        - op 路径:start_running → op_factory(ctx) → op.execute() → stop_running。

        任何异常都固化终态(镜像原 RunSlot 安全网),避免卡 terminal_state=None/RUNNING。
        """
        ctx = self._ctx
        run_context = ctx.run_context
        result: OperationResult | None = None
        failed_node: str | None = None
        try:
            if app_id is not None:
                # —— app 路径:委托 run_application(共享入口)——
                if refresh_config is not None:
                    refresh_config()                       # 槽线程内、_start 已赢锁后、run_application 前(修刷新竞态)
                # 刷新后再读实例下标(refresh_config 可能切实例),修 instance_idx 回归
                run_context.current_instance_idx = ctx.current_instance_idx
                try:
                    self.app = run_context.get_application_name(app_id)   # 固化应用中文名
                except Exception:  # noqa: BLE001
                    self.app = app_id
                run_result = run_context.run_application(
                    app_id, run_context.current_instance_idx, group_id
                )
                if run_result.finish_reason == RunFinishReason.NOT_STARTED:
                    result = OperationResult(
                        success=False,
                        status=f'应用运行失败: {run_result.finish_reason}',
                    )
                else:
                    result = run_context.last_application_result
                    if result is None:
                        result = OperationResult(
                            success=False,
                            status=f'应用运行失败: {run_result.finish_reason}',
                        )
            else:
                # —— op 路径:槽自管生命周期(open_game / 自定义 op 通用)——
                run_context.current_instance_idx = instance_idx if instance_idx is not None else ctx.current_instance_idx
                if not run_context.start_running():
                    result = OperationResult(success=False, status='start_running 失败(有其它运行)')
                else:
                    op: Operation | None = None
                    try:
                        op = op_factory(ctx)
                        with self._lock:
                            self.current_op = op
                            if self.op_id is None:
                                self.op_id = op.__class__.__name__   # open_game 未传 display_name 时 fallback 类名
                            self.app = op.op_name or op.__class__.__name__   # 优先 Operation.op_name(中文),空时类名
                        result = op.execute()
                    except Exception as e:  # noqa: BLE001 execute 抛异常也兜住,避免卡 RUNNING
                        result = OperationResult(success=False, status=f'执行异常: {e}')
                    finally:
                        # 清除句柄前本地捕获失败节点(修 failed_node 丢失),与原 RunSlot 一致
                        failed_node = getattr(getattr(op, '_current_node', None), 'cn', None) if op is not None else None
                        with self._lock:
                            self.current_op = None
                        run_context.stop_running()
        except Exception as e:  # noqa: BLE001 兜底:refresh_config/run_application 等抛异常也固化,避免卡 RUNNING
            result = OperationResult(success=False, status=f'执行异常: {e}')
        finally:
            # —— 固化终态(任何路径都执行,镜像原 RunSlot finally)——
            terminal = (RunState.SUCCESS if (result is not None and result.success)
                        else RunState.STOPPED if (result is not None and result.status == '人工结束')
                        else RunState.FAILED)
            if failed_node is None:
                failed_node = self._node_name() or (result.status if result is not None else None)
            with self._lock:
                self.terminal_state = terminal
                self.last_status = result.status if result is not None else '执行异常'
                self.failed_node = failed_node if terminal == RunState.FAILED else None   # 仅 FAILED 记失败节点
                self.finished_at = time.time()
        return result

    def _node_name(self) -> str | None:
        """统一读进度句柄的当前节点(app 路径读 current_application,op 路径读 current_op)。"""
        op = self.current_op or self._ctx.run_context.current_application
        node = getattr(op, '_current_node', None) if op is not None else None
        return getattr(node, 'cn', None) if node is not None else None

    def _query_status(self) -> RunStatusResult:
        """查询运行状态。判据用固化 terminal_state(单一事实源),不读 run_context。

        终态:返固化 terminal_state + last_status/failed_node。
        运行中(started_at 非 None 且 terminal_state None):统一 RUNNING,
        进度读 progress = current_op or run_context.current_application(Application 也是 Operation)。
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
        # 进度句柄:op 路径读 current_op,app 路径(current_op=None)读 run_context.current_application
        progress = op if op is not None else self._ctx.run_context.current_application
        node = getattr(progress, '_current_node', None) if progress is not None else None
        current_node = getattr(node, 'cn', None) if node is not None else None
        retry_count = getattr(progress, 'node_retry_times', None) if progress is not None else None
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


def _save_screenshot(image: 'MatLike') -> str:
    """将 RGB 截图以 BGR 写盘到 ``.debug/zzz_od_mcp/screenshot/``,返回绝对路径。

    Args:
        image: backend ``capture`` / ``analyze`` 截到的 RGB ``ndarray``。

    Returns:
        保存后的截图文件绝对路径。

    Raises:
        RuntimeError: ``cv2.imwrite`` 写盘失败时抛出。
    """
    import cv2

    screenshot_dir = Path(os_utils.get_path_under_work_dir('.debug', 'zzz_od_mcp', 'screenshot'))
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    img_path = screenshot_dir / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    bgr_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if not cv2.imwrite(str(img_path), bgr_image):
        raise RuntimeError(f'截图写盘失败: {img_path}')
    return str(img_path)


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

    def _refresh_runtime_config(self) -> None:
        """刷新外部 GUI 可能已经写入 YAML 的运行配置。

        MCP server 是独立进程，GUI 修改配置后不会自动更新本进程内的
        ``YamlConfig`` / ``ApplicationFactory`` 缓存。运行前刷新一次，可减少
        独立应用选择、体力计划、自动战斗配置等与 GUI 设置不一致的问题。
        """
        # one_dragon_config 是 cached_property；删除缓存后会从 YAML 重新构造。
        if 'one_dragon_config' in self._ctx.__dict__:
            del self._ctx.__dict__['one_dragon_config']
        active_instance = self._ctx.one_dragon_config.current_active_instance
        active_instance_idx = getattr(active_instance, 'idx', None)
        if isinstance(active_instance_idx, int) and active_instance_idx != self._ctx.current_instance_idx:
            # GUI 改了当前启用实例时，server 进程要同步切到同一个实例再运行。
            self._ctx.current_instance_idx = active_instance_idx
            self._ctx.reload_instance_config()
            self._ctx.on_switch_instance()
        else:
            self._ctx.reload_instance_config()
        # 应用配置和运行记录在工厂里有缓存；运行前清掉，下一次读取会落到最新 YAML。
        self._ctx.run_context.clear_application_cache()
        self._ctx.app_group_manager.clear_config_cache()

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
        # 打码 UID:对齐 controller.screenshot()(框架流程截图本就经 fill_uid_black 打码,
        # backend 截图供 MCP/HTTP 落盘 / 外传,同样不能带账号信息)。
        return controller.fill_uid_black(image)

    @staticmethod
    def _resolve_screenshot(screenshot: str) -> 'tuple[MatLike | None, str]':
        """把 screenshot(绝对路径或 debug 图名)解析为(图像, 解析后完整路径)。

        绝对路径按路径读;否则当 ``.debug/images`` 下的 debug 图名,自动补 ``.png``。
        图像读不到时返回 ``(None, 解析后路径)``,由调用方报错。

        Args:
            screenshot: 截图绝对路径,或 ``.debug/images`` 下的图名(不带后缀)。

        Returns:
            (image, resolved_path):image 为 RGB ndarray,文件不存在/不可读时为 None。
        """
        if Path(screenshot).is_absolute():
            resolved = screenshot
        else:
            resolved = debug_utils.get_debug_image_path(screenshot)
        return cv2_utils.read_image(resolved), resolved

    def analyze(self, screenshot: str | None = None, save_image: bool = False) -> AnalyzeScreenResult:
        """分析画面:截图 + 全图 OCR + 画面匹配(精准/模糊)。

        screenshot 省略 → 截当前游戏画面(需游戏窗口就绪);精准命中回写
        ``ctx.screen_loader.update_current_screen_name``,为下次 BFS 提供起点。
        screenshot 传入 → 解析指定截图,**无需游戏窗口就绪**:绝对路径按路径读,
        纯名字到 ``.debug/images/<名字>.png`` 读;读不到返失败(error 带解析后完整路径)。
        **不回写**识别状态(离线 / 可能是旧图,不污染实时识别)。

        save_image=True(**仅实时模式生效**)→ 把截到的内存图落盘到
        ``.debug/zzz_od_mcp/screenshot/``,路径写入 ``screenshot_path`` 返回,
        供调用方喂给 vision 复用(省掉第二次截图)。离线模式忽略(调用方本就有路径)。

        Args:
            screenshot: 截图绝对路径,或 ``.debug/images`` 下的图名(不带后缀);
                None 表示实时截当前画面。
            save_image: 实时模式下是否把截图落盘并回传路径(默认 False)。

        Returns:
            分析结果:成功标志、OCR 文本列表、画面匹配列表、错误描述、
            screenshot_path(本次新存的截图路径,实时+save_image=True 时有值)、
            vision_hint(成功时填的能力边界提示,失败时 None)。
        """
        self._ensure_ready()
        should_save: bool = save_image and screenshot is None
        saved_path: str | None = None
        if screenshot is None:
            controller = self._ctx.controller
            if controller is None or not controller.is_game_window_ready:
                return AnalyzeScreenResult(success=False, ocr_texts=[], screens=[], error='游戏窗口未就绪')
            image = controller.get_screenshot(independent=False)
            if image is None:
                return AnalyzeScreenResult(success=False, ocr_texts=[], screens=[], error='截图失败')
            # 打码 UID:对齐 controller.screenshot(),analyze 的 OCR / 画面匹配不依赖 UID 区域。
            image = controller.fill_uid_black(image)
            write_back = True
        else:
            image, resolved = self._resolve_screenshot(screenshot)
            if image is None:
                return AnalyzeScreenResult(success=False, ocr_texts=[], screens=[], error=f'读取截图失败: {resolved}')
            write_back = False
        try:
            if should_save:
                saved_path = _save_screenshot(image)  # 写盘失败抛错,由本 except 兜住
            # crop_first=False:与下方 find_screen_matches 内 find_area_with_detail(color_range=None)复用
            # 同一份全图 OCR 缓存(cache key 含 crop_first;True/False 不复用会触发两次全图 OCR)。
            # rect=None 时 crop_first 不影响 OCR 结果(都全图),只改 cache key。
            ocr_result_list = self._ctx.ocr_service.get_ocr_result_list(image=image, crop_first=False)
            ocr_texts = [
                OcrText(text=r.data, x=int(r.x), y=int(r.y), width=int(r.w), height=int(r.h))
                for r in ocr_result_list
            ]
            screens = find_screen_matches(self._ctx, image)
            if write_back and screens and screens[0].is_precise:
                self._ctx.screen_loader.update_current_screen_name(screens[0].screen_name)
            return AnalyzeScreenResult(success=True, ocr_texts=ocr_texts, screens=screens, error=None,
                                       screenshot_path=saved_path, vision_hint=_VISION_HINT)
        except Exception as e:  # noqa: BLE001 OCR/匹配/存盘异常兜底:不回写,返失败(存盘已成功的仍回传路径排障)
            return AnalyzeScreenResult(success=False, ocr_texts=[], screens=[], error=str(e), screenshot_path=saved_path)

    def upsert_screen_area(
        self,
        screen_name: str,
        area_name: str,
        pc_rect: list[int],
        text: str = '',
        lcs_percent: float = 0.5,
        template_sub_dir: str = '',
        template_id: str = '',
        template_match_threshold: float = 0.7,
        color_range: list[list[int]] | None = None,
        goto_list: list[str] | None = None,
        id_mark: bool = False,
        gamepad_key: str | None = None,
    ) -> dict:
        """按 area_name 在指定 screen 插入或更新一个 area(写 yml + reload)。操作类。

        area_name 已存在 → 整体更新;不存在 → 追加。写回 screen_info yml 并重载,
        下次 analyze_screen 即生效。无需游戏窗口在线。

        Args:
            screen_name: 目标画面名(中文,对齐 get_screen / analyze 返回)。
            area_name: 区域名(同 screen 内唯一,作匹配键)。
            pc_rect: ``[x1, y1, x2, y2]``,1920×1080 内、x2>x1、y2>y1。
            text: 文本区域的 OCR 文本(空则非文本区)。
            lcs_percent: 文本匹配阈值。
            template_sub_dir / template_id: 模板引用;template_id 非空时模板必须存在,否则阻断。
            template_match_threshold: 模板匹配阈值。
            color_range: 文本颜色筛选 ``[[lower], [upper]]`` 或 None。
            goto_list: 交互后可能跳转的画面名列表。
            id_mark: 是否画面唯一标识。
            gamepad_key: 手柄动作名。

        Returns:
            ``{success, screen_name, area_name, action(inserted/updated), area_count, error}``。
        """
        try:
            if not area_name:
                return _area_result(False, screen_name, area_name, None, error='area_name 不能为空')
            rect_msg = _validate_pc_rect(pc_rect)
            if rect_msg is not None:
                return _area_result(False, screen_name, area_name, None, error=rect_msg)
            if template_id and self._ctx.template_loader.load_template(template_sub_dir, template_id) is None:
                return _area_result(False, screen_name, area_name, None,
                                    error=f'模板不存在: {template_sub_dir}/{template_id}')
            area = ScreenArea(
                area_name=area_name,
                pc_rect=Rect(int(pc_rect[0]), int(pc_rect[1]), int(pc_rect[2]), int(pc_rect[3])),
                text=text, lcs_percent=lcs_percent,
                template_id=template_id, template_sub_dir=template_sub_dir,
                template_match_threshold=template_match_threshold,
                color_range=color_range, goto_list=goto_list or [],
                id_mark=id_mark, gamepad_key=gamepad_key,
            )
            screen_info = self._ctx.screen_loader.get_screen(screen_name)  # 未找到 raise
            action = screen_info.upsert_area(area)
            self._ctx.screen_loader.save_screen(screen_info)
            return _area_result(True, screen_name, area_name, action, count=len(screen_info.area_list))
        except Exception as e:  # noqa: BLE001 工具层兜底,不向 MCP 透传
            return _area_result(False, screen_name, area_name, None, error=str(e),
                                count=self._safe_area_count(screen_name))

    def delete_screen_area(self, screen_name: str, area_name: str) -> dict:
        """按 area_name 删除指定 screen 的一个 area(写 yml + reload)。操作类。

        Args:
            screen_name: 目标画面名。
            area_name: 要删除的区域名;不存在则报错。

        Returns:
            ``{success, screen_name, area_name, action(deleted), area_count, error}``。
        """
        try:
            if not area_name:
                return _area_result(False, screen_name, area_name, None, error='area_name 不能为空')
            screen_info = self._ctx.screen_loader.get_screen(screen_name)  # 未找到 raise
            if not screen_info.remove_area_by_name(area_name):
                return _area_result(False, screen_name, area_name, None,
                                    error=f'未找到 area: {area_name}', count=len(screen_info.area_list))
            self._ctx.screen_loader.save_screen(screen_info)
            return _area_result(True, screen_name, area_name, 'deleted', count=len(screen_info.area_list))
        except Exception as e:  # noqa: BLE001 工具层兜底
            return _area_result(False, screen_name, area_name, None, error=str(e),
                                count=self._safe_area_count(screen_name))

    def _safe_area_count(self, screen_name: str) -> int | None:
        """异常路径下尽量取 area 数(取不到返 None,不再抛)。"""
        try:
            return len(self._ctx.screen_loader.get_screen(screen_name).area_list)
        except Exception:  # noqa: BLE001
            return None

    def close_game(self) -> str:
        """关闭游戏(发关闭窗口信号,秒级,不走运行槽)。

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

    def click_game(self, x: int | float, y: int | float, press_time: float = 0.1, pc_alt: bool = False) -> dict:
        """点击游戏窗口内指定坐标(1080p 游戏空间,同源 screen_info pc_rect)。操作类。

        坐标经控制器自动缩放到真实屏幕。坐标不在游戏窗口内时控制器返 False(不点击)。

        Args:
            x, y: 默认分辨率(1920×1080)下的游戏窗口坐标。
            press_time: >0 时长按若干秒。
            pc_alt: 点击前是否先按住 Alt 解锁光标。大世界等 ``pc_alt=true`` 画面必需
                (绝区零会锁光标,不按 Alt 点击落空);其余画面保持 False。

        Returns:
            ``{success, x, y, in_window, pc_alt}``:``success/in_window=False`` 表示坐标不在窗口内。

        Raises:
            BackendNotReadyError: ZContext 未就绪或游戏窗口未就绪时抛。
        """
        self._ensure_ready()
        controller = self._ctx.controller
        if controller is None or not controller.is_game_window_ready:
            raise BackendNotReadyError('游戏窗口未就绪')
        controller.active_window()
        clicked = controller.click(Point(int(x), int(y)), press_time=press_time, pc_alt=pc_alt)
        return {'success': clicked, 'x': int(x), 'y': int(y), 'in_window': clicked, 'pc_alt': pc_alt}

    def key_tap(self, key: str, press_time: float = 0.0) -> dict:
        """键盘按键:``press_time=0`` 短按(tap),``press_time>0`` 长按(press→保持→release)。操作类。

        覆盖框架 ``btn_controller`` 能发的键:移动 ``w``/``a``/``s``/``d``、交互 ``f``、
        ``esc``、``space`` 等。键名沿用框架约定。需游戏窗口就绪。

        Args:
            key: 按键名(如 ``'w'``/``'f'``/``'esc'``/``'space'``)。
            press_time: >0 时长按若干秒(如移动长按 1-2s);=0 短按。

        Returns:
            ``{success, key, press_time}``。

        Raises:
            BackendNotReadyError: ZContext / 游戏窗口未就绪时抛。
        """
        self._ensure_ready()
        controller = self._ctx.controller
        if controller is None or not controller.is_game_window_ready:
            raise BackendNotReadyError('游戏窗口未就绪')
        controller.active_window()
        if press_time > 0:
            controller.btn_controller.press(key, press_time=press_time)
        else:
            controller.btn_tap(key)
        return {'success': True, 'key': key, 'press_time': press_time}

    def drag(self, x1: int | float, y1: int | float, x2: int | float, y2: int | float, duration: float = 1.0) -> dict:
        """鼠标按住拖拽:从 (x1,y1) 拖到 (x2,y2),持续 duration 秒。操作类。

        1080p 游戏空间坐标(同 screen_info ``pc_rect``)。覆盖刮刮卡刮开、八卦收集
        来回拖、咖啡拖动等。需游戏窗口就绪。

        Args:
            x1, y1: 起点坐标(1920×1080)。
            x2, y2: 终点坐标。
            duration: 拖拽持续秒数(默认 1.0)。

        Returns:
            ``{success, x1, y1, x2, y2, duration}``。

        Raises:
            BackendNotReadyError: ZContext / 游戏窗口未就绪时抛。
        """
        self._ensure_ready()
        controller = self._ctx.controller
        if controller is None or not controller.is_game_window_ready:
            raise BackendNotReadyError('游戏窗口未就绪')
        controller.active_window()
        controller.drag_to(Point(int(x2), int(y2)), start=Point(int(x1), int(y1)), duration=duration)
        return {'success': True, 'x1': int(x1), 'y1': int(y1), 'x2': int(x2), 'y2': int(y2), 'duration': duration}

    def input_text(self, text: str, use_clipboard: bool | None = None) -> dict:
        """向当前焦点输入框输入文本(账号/密码等)。操作类。

        use_clipboard=None → 跟随 ``game_config.type_input_way``(同 ``EnterGame``);
        True/False → 强制剪贴板/逐键。输入前激活游戏窗口(键盘注入 / Ctrl+V 均需前台焦点)。

        Args:
            text: 要输入的文本。
            use_clipboard: True=剪贴板(copy_and_paste,支持中文/特殊字符);
                False=逐键(controller.input_str);None=跟随全局配置。

        Returns:
            ``{success, method, masked_text}``:method ∈ {'clipboard','keyboard'};
            masked_text 为脱敏文本。

        Raises:
            BackendNotReadyError: ZContext 未就绪或游戏窗口未就绪时抛。
        """
        self._ensure_ready()
        controller = self._ctx.controller
        if controller is None or not controller.is_game_window_ready:
            raise BackendNotReadyError('游戏窗口未就绪')
        use_cb = self._resolve_use_clipboard(use_clipboard)
        controller.active_window()
        if use_cb:
            PcClipboard.copy_and_paste(text)
            method = 'clipboard'
        else:
            controller.input_str(text)
            method = 'keyboard'
        return {'success': True, 'method': method, 'masked_text': mask_text(text)}

    def _resolve_use_clipboard(self, use_clipboard: bool | None) -> bool:
        """解析输入方式:非 None 原样返回;None 读 game_config.type_input_way(== CLIPBOARD 则 True)。"""
        if use_clipboard is not None:
            return use_clipboard
        return self._ctx.game_config.type_input_way == TypeInputWay.CLIPBOARD.value.value

    def start_run(
        self,
        source: str,
        op_factory: 'Callable[[ZContext], Operation]',
        display_name: str | None = None,
    ) -> tuple[bool, Future | None]:
        """触发运行(op 原语入口,供 open_game 等经适配器调用)。

        单跑道委托 ``run_slot._start``(op 路径):已有运行在进行时返回 ``ok=False``，
        适配器据此返回并发拒绝；其余由 RunSlot 在后台线程内执行 operation。
        单跑道互斥由 ``run_slot._start`` 锁内 check-then-submit 原子保证。

        Args:
            source: 触发方标识，如 ``"mcp"``/``"http"``。
            op_factory: operation 构造器，由适配器提供。
            display_name: op 路径定位标识(如 op_id);None 时 _run 内 fallback 类名。

        Returns:
            ``(ok, future)``：``ok=False`` 表示已有运行在进行(``future=None``)；
            ``ok=True`` 表示已启动，``future`` 可供阻塞 await 取结果。
        """
        return self.run_slot._start(source, op_factory=op_factory, display_name=display_name)

    def run_one_dragon(self, source: str) -> tuple[bool, Future | None]:
        """按当前一条龙配置启动完整一条龙运行(app 路径,经 ``_start_app``)。"""
        self._ensure_ready()
        return self._start_app(source, application_const.ONE_DRAGON_APP_ID, application_const.DEFAULT_GROUP_ID)

    def run_standalone_app(self, source: str, app_id: str | None = None) -> tuple[bool, Future | None]:
        """启动独立应用；app_id 为空时使用 GUI 当前选中的独立应用(app 路径,经 ``_start_app``)。"""
        self._ensure_ready()
        target_app_id = app_id or self._ctx.standalone_app_config.active_app_id
        if not target_app_id:
            raise BackendNotReadyError('未选择独立应用')
        return self._start_app(source, target_app_id, application_const.DEFAULT_GROUP_ID)

    def _start_app(self, source: str, app_id: str, group_id: str) -> tuple[bool, Future | None]:
        """app 路径统一入口:委托 ``run_slot._start`` 的 app 分派。

        ``refresh_config`` 作为钩子注入槽线程:仅在 ``_start`` 赢锁后、``run_application``
        前执行(拒绝路径不进 ``_run``,不刷新),修原 ``run_one_dragon``/``run_standalone_app``
        的刷新竞态;``instance_idx`` 由 ``_run`` 在刷新后重读(可能切实例)。

        Args:
            source: 触发方标识。
            app_id: 应用 id(同时作唯一标识 op_id)。
            group_id: 应用组 id。

        Returns:
            ``(ok, future)``:``ok=False`` 表示单跑道已有运行在跑。
        """
        return self.run_slot._start(
            source, app_id=app_id, group_id=group_id,
            instance_idx=self._ctx.current_instance_idx,
            refresh_config=self._refresh_runtime_config,
        )

    def list_applications(self) -> ApplicationListResult:
        """列出当前实例可运行应用和独立应用选择状态(只读路径,不刷新配置)。"""
        self._ensure_ready()
        active_standalone_app_id = self._ctx.standalone_app_config.active_app_id
        standalone_app_ids = set(self._ctx.standalone_app_config.app_list)
        group_config = self._ctx.app_group_manager.get_one_dragon_group_config(self._ctx.current_instance_idx)
        enabled_map = {item.app_id: item.enabled for item in group_config.app_list}

        # 展示顺序与运行语义一致：先固定一条龙入口，再追加默认组注册的独立应用。
        app_ids: list[str] = []
        if self._ctx.run_context.is_app_registered(application_const.ONE_DRAGON_APP_ID):
            app_ids.append(application_const.ONE_DRAGON_APP_ID)
        for app_id in self._ctx.run_context.default_group_apps:
            if app_id not in app_ids:
                app_ids.append(app_id)

        applications: list[ApplicationInfo] = []
        for app_id in app_ids:
            try:
                app_name = self._ctx.run_context.get_application_name(app_id)
            except Exception:  # noqa: BLE001 应用列表用于展示，跳过异常名称
                app_name = app_id
            applications.append(ApplicationInfo(
                app_id=app_id,
                app_name=app_name,
                enabled_in_one_dragon=enabled_map.get(app_id, False),
                in_standalone_list=app_id in standalone_app_ids,
                is_active_standalone=app_id == active_standalone_app_id,
            ))
        return ApplicationListResult(
            current_instance_idx=self._ctx.current_instance_idx,
            active_standalone_app_id=active_standalone_app_id,
            applications=applications,
        )

    def list_predefined_teams(self) -> PredefinedTeamListResult:
        """列出当前实例的预备编队(只读,过滤 ``TeamConfig`` 自动补的占位)。

        返回真实配队(idx/name/auto_battle/agent_id_list/weakness_list);
        ``weakness_list`` 为中文弱点(防卫战配置优先,没配取角色伤害属性);
        ``idx`` 可直接喂给 ``ChoosePredefinedTeam`` op 的 ``target_team_idx_list``。

        快照语义(对齐 ``list_applications``):读当前进程缓存的 ``team_config``,
        不主动刷新;GUI 改 yml 后需重载实例 / 跑 app 触发刷新缓存才反映。
        """
        self._ensure_ready()
        team_cfg = self._ctx.team_config
        raw_count = len(team_cfg.get('team_list', []))  # yml 真实队数(不含自动补的占位)
        teams: list[PredefinedTeamItem] = []
        for t in team_cfg.team_list[:raw_count]:
            teams.append(PredefinedTeamItem(
                idx=t.idx, name=t.name, auto_battle=t.auto_battle,
                agent_id_list=list(t.agent_id_list),
                agent_name_list=[getattr(_AGENT_MAP.get(aid), 'agent_name', aid) for aid in t.agent_id_list],
                weakness_list=self._weakness_of_team(t),
            ))
        return PredefinedTeamListResult(
            current_instance_idx=self._ctx.current_instance_idx,
            teams=teams,
        )

    def _get_shiyu_defense_config(self) -> 'ShiyuDefenseConfig | None':
        """取当前实例的防卫战配置(app 未注册 → None;已注册则加载失败向上抛,不吞)。

        先用 ``is_app_registered`` 判(对齐 ``list_applications``),避免框架裸 ``Exception``
        下宽 ``except`` 把 YAML / 类型 / I/O 加载错误也当「未配置」静默吞掉、错误回退弱点。
        """
        if not self._ctx.run_context.is_app_registered(shiyu_defense_const.APP_ID):
            return None
        return self._ctx.run_context.get_config(
            app_id=shiyu_defense_const.APP_ID,
            instance_idx=self._ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

    def _weakness_of_team(self, team: 'PredefinedTeamInfo') -> list[str]:
        """推导队伍弱点(中文):① 防卫战配置的 weakness_list 优先;② 没配取角色伤害属性。"""
        # ① 防卫战配置
        defense_cfg = self._get_shiyu_defense_config()
        if defense_cfg is not None:
            dc = defense_cfg.get_config_by_team_idx(team.idx)
            if dc is not None and dc.weakness_list:
                weakness = [w.value for w in dc.weakness_list if w != DmgTypeEnum.UNKNOWN]
                if weakness:
                    return weakness
        # ② 没配 → 角色伤害属性(去重,跳过 unknown)
        weakness: list[str] = []
        for agent_id in team.agent_id_list:
            if agent_id == 'unknown':
                continue
            agent = _AGENT_MAP.get(agent_id)
            if agent is not None and agent.dmg_type != DmgTypeEnum.UNKNOWN:
                if agent.dmg_type.value not in weakness:
                    weakness.append(agent.dmg_type.value)
        return weakness

    def query_status(self) -> RunStatusResult:
        """查询当前或最近一次运行状态(单槽,直接委托)。"""
        return self.run_slot._query_status()

    def stop(self) -> dict:
        """停止当前运行(单槽)。无运行时返回 ``{stopped: False, error}``。"""
        stopped, source = self.run_slot._stop()
        if stopped:
            return {'stopped': True, 'source': source}
        return {'stopped': False, 'error': '当前无运行'}

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
