"""在编辑器里试跑一条路线：切到游戏，按打点顺序走一遍，不衔接其他路线。

这是给路线本身做的自检工具，不参与正式跑图，也不改变正式运行的开启选择：
正式跑图由 BagelApp 调起同样的 BagelRouteWalker 并衔接结算。关闭的路线也可以
试跑，但角色必须站在该路线绑定的出生点。

试跑期间挂一个执行态悬浮窗，显示自绘小地图、当前决策与路线进度。
"""

from __future__ import annotations

import time
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_route_model import BagelRouteRef
from zzz_od.application.bagel.bagel_route_recorder import is_foreground
from zzz_od.application.bagel.bagel_route_walker import BagelRouteWalker
from zzz_od.game_data.map_locator.map_locator import load_map_locators
from zzz_od.gui.view.bagel.bagel_run_overlay import KIND_LABELS

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from zzz_od.context.zzz_context import ZContext

GAME_FOREGROUND_TIMEOUT: float = 5.0
"""切到游戏前台的最长等待秒数。"""

STATE_INTERVAL: float = 0.25
"""向悬浮窗推送状态的间隔（秒）。"""


class BagelRouteTestThread(QThread):
    """把一次路线试跑放到后台线程，避免卡住编辑器界面。"""

    status_changed = Signal(str)
    """当前阶段文案。"""

    overlay_state = Signal(object)
    """推给悬浮窗的状态字典；None 表示收起悬浮窗。"""

    done = Signal(bool, str)
    """(是否成功, 结论文案)。"""

    def __init__(
        self, ctx: ZContext, route_ref: BagelRouteRef, parent: QWidget | None = None,
    ) -> None:
        """
        Args:
            ctx: 运行上下文。
            route_ref: 要试跑的路线。
            parent: Qt 父对象。
        """
        super().__init__(parent)
        self.ctx: ZContext = ctx
        self.route_ref: BagelRouteRef = route_ref
        self._stop_requested: Event = Event()
        self._owns_run: bool = False
        """本线程是否已取得共享运行状态；只有取得后，停止试跑才能结束运行状态。"""
        self._walker: BagelRouteWalker | None = None
        self._layer_images: dict[str, Path] = {}

    def run(self) -> None:
        """切到游戏后执行一次路线，结束后恢复空闲状态。"""
        try:
            if not self._activate_game():
                self.done.emit(False, '游戏窗口未切到前台，未开始试跑')
                return
            self.status_changed.emit('试跑中，按打点顺序移动')
            self._layer_images = {item.name: item.image_path for item in load_map_locators()}
            # 先占用运行状态再创建执行器：执行器一创建就启动输入线程，
            # 占用失败时不能留下没人收尾的线程。
            if not self.ctx.run_context.start_running():
                self.done.emit(False, '当前有其他功能在运行，请先结束它再试跑')
                return
            # 先登记运行权再检查停止请求：stop() 若在登记前到达，这里能看到停止请求；
            # 若在登记后到达，stop() 会结束运行状态，执行器随即退出。
            self._owns_run = True
            if self._stop_requested.is_set():
                self.done.emit(False, '已手动停止试跑')
                return
            self._walker = BagelRouteWalker(self.ctx, route_ref=self.route_ref)
            result = self._run_with_state()
        except ValueError as error:
            self.done.emit(False, str(error))
            return
        except Exception as error:
            log.error('贝果路线试跑异常', exc_info=True)
            self.done.emit(False, f'试跑异常：{error}')
            return
        finally:
            self.overlay_state.emit(None)
            self._restore_idle()

        if self._stop_requested.is_set():
            self.done.emit(False, '已手动停止试跑')
            return
        if result.success:
            points = len(self._walker.routes[0].points) if self._walker and self._walker.routes else 0
            self.done.emit(True, f'试跑完成，{points} 点走完：{result.status}')
            return
        detail = f'：{result.data}' if isinstance(result.data, str) and result.data else ''
        self.done.emit(False, f'试跑失败：{result.status}{detail}')

    def _run_with_state(self):
        """跑执行器，同时按固定间隔把状态推给悬浮窗。

        execute() 是阻塞调用，所以状态推送放在一个旁路线程里，
        靠停止事件退出，避免往主循环里插轮询。
        """
        walker = self._walker
        if walker is None:
            raise ValueError('执行器未创建')
        reporter = _StateReporter(
            walker, self.overlay_state, self._layer_images, self._stop_requested,
        )
        reporter.start()
        try:
            return walker.execute()
        finally:
            reporter.request_stop()
            reporter.wait(2000)

    def stop(self) -> None:
        """请求停止试跑；未取得运行状态时只设停止标记，不影响其他功能的运行。"""
        self._stop_requested.set()
        if self._owns_run:
            self.ctx.run_context.stop_running()

    def _activate_game(self) -> bool:
        """把游戏窗口切到前台并等它真的在前台。"""
        controller = self.ctx.controller
        game_win = controller.game_win
        hwnd = game_win.get_hwnd()
        if hwnd is None or not controller.is_game_window_ready:
            return False
        controller.active_window()
        deadline = time.monotonic() + GAME_FOREGROUND_TIMEOUT
        while time.monotonic() < deadline:
            if self._stop_requested.is_set():
                return False
            if is_foreground(hwnd):
                return True
            time.sleep(0.2)
        return False

    def _restore_idle(self) -> None:
        """试跑结束把运行上下文交回空闲，避免编辑器留着「运行中」。"""
        try:
            self.ctx.controller.stop_moving_forward()
        except Exception:
            log.error('试跑收尾松开前进键失败', exc_info=True)
        if not self.ctx.run_context.is_context_stop:
            self.ctx.run_context.stop_running()


class _StateReporter(QThread):
    """按固定间隔把执行器状态整理成悬浮窗要的字段。"""

    def __init__(
        self, walker: BagelRouteWalker, signal, layer_images: dict[str, Path],
        stop: Event,
    ) -> None:
        """
        Args:
            walker: 正在执行的路线执行器。
            signal: 向外发状态的 Qt 信号。
            layer_images: 分层名到层底图路径。
            stop: 试跑的停止事件。
        """
        super().__init__()
        self.walker: BagelRouteWalker = walker
        self.signal = signal
        self.layer_images: dict[str, Path] = layer_images
        self.stop_event: Event = stop
        self._stop: Event = Event()

    def request_stop(self) -> None:
        """请求退出旁路线程。"""
        self._stop.set()

    def run(self) -> None:
        """循环推送状态直到被要求停止。"""
        while not self._stop.is_set() and not self.stop_event.is_set():
            try:
                snapshot = self.walker.state_snapshot()
            except Exception:
                log.error('读取执行状态失败', exc_info=True)
                return
            snapshot['layer_image'] = self.layer_images.get(str(snapshot.get('layer', '')))
            self.signal.emit(snapshot)
            time.sleep(STATE_INTERVAL)


def decision_lines(snapshot: dict[str, object]) -> list[str]:
    """把状态快照整理成悬浮窗的文本行。

    Args:
        snapshot: 执行器给出的状态字典。

    Returns:
        逐行文本：节点、状态、路线进度、当前目标。
    """
    cursor = int(snapshot.get('cursor') or 0)
    total = int(snapshot.get('total') or 0)
    route_name = str(snapshot.get('route_name') or snapshot.get('route_id') or '')
    points = snapshot.get('points') or []
    # 决策文字是「节点 · 状态」，状态里也可能带「·」，只按第一个拆成两行。
    node, _, status = str(snapshot.get('decision') or '准备中').partition(' · ')
    lines = [f'节点 {node}', f'状态 {status or "—"}']
    lines.append(f'路线 {route_name} · {cursor}/{total}' if route_name else '路线 识别出生点中')
    distance = snapshot.get('distance')
    distance_text = '—' if distance is None else f'{float(distance):.0f}px'
    if 0 <= cursor < len(points):
        kind = points[cursor][0]
        lines.append(f'目标 {KIND_LABELS.get(kind, kind)}（{distance_text}）')
    else:
        lines.append(f'目标 —（{distance_text}）')
    return lines
