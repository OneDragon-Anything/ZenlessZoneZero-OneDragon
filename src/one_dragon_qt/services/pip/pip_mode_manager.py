from __future__ import annotations

from cv2.typing import MatLike
from PySide6.QtCore import QTimer

from one_dragon.base.controller.pc_controller_base import PcControllerBase
from one_dragon.base.controller.pc_screenshot.pc_screenshot_controller import (
    PcScreenshotController,
)
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.log_utils import log
from one_dragon_qt.services.pip.pip_capture_worker import PipCaptureWorker
from one_dragon_qt.widgets.pip_window import PipWindow


class PipModeManager:
    """画中画模式管理器

    开启后轮询游戏窗口状态：
    - 游戏切到后台 -> 自动显示画中画 + 恢复截图
    - 游戏切到前台 -> 自动隐藏画中画 + 暂停截图
    - 画中画被点击 -> 游戏切到前台
    - 画中画被右键关闭 -> 隐藏并暂停截图，下次游戏切前台后重置
    """

    POLL_INTERVAL_MS: int = 200

    def __init__(self, ctx: OneDragonContext) -> None:
        self.ctx = ctx
        self._controller: PcControllerBase | None = None
        self._pip_window: PipWindow | None = None
        self._worker: PipCaptureWorker | None = None
        self._screenshot_ctrl: PcScreenshotController | None = None
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._on_poll)
        self._active: bool = False
        self._dismissed: bool = False

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self) -> bool:
        """开启画中画模式。即使游戏尚未启动也会进入轮询等待。"""
        if self._active:
            return True

        if self.ctx.controller is None:
            self.ctx.init_controller()

        self._active = True
        self._poll_timer.start(self.POLL_INTERVAL_MS)
        return True

    def pause(self) -> None:
        """暂停轮询和截图，保留资源。可通过 resume 恢复。"""
        self._poll_timer.stop()
        if self._worker is not None:
            self._worker.pause()
        if self._pip_window is not None:
            self._pip_window.hide()

    def resume(self) -> None:
        """恢复轮询。"""
        if self._active:
            self._poll_timer.start(self.POLL_INTERVAL_MS)

    def stop(self) -> None:
        """关闭画中画模式，释放所有资源。"""
        self._active = False
        self._poll_timer.stop()
        self._release_resources()

    def _release_resources(self) -> None:
        """释放截图/worker/window 资源，但不改变 _active 状态。"""
        if self._worker is not None:
            self._worker.stop()
            if self._pip_window is not None:
                self._worker.frame_ready.disconnect(self._pip_window.on_frame_ready)
            self._worker = None
        if self._pip_window is not None:
            self._pip_window.closed.disconnect(self._on_pip_closed)
            self._pip_window.clicked.disconnect(self._on_pip_clicked)
            self._pip_window.hide()
            self._pip_window.deleteLater()
            self._pip_window = None
        if self._screenshot_ctrl is not None:
            self._screenshot_ctrl.cleanup()
            self._screenshot_ctrl = None
        self._controller = None

    def _on_poll(self) -> None:
        """轮询游戏窗口前台状态。

        三个阶段:
        1. 等待 controller 出现（游戏未启动时）
        2. 等待游戏窗口就绪并初始化截图控制器
        3. 前台/后台切换逻辑
        """
        try:
            self._do_poll()
        except Exception:
            log.error('画中画轮询异常', exc_info=True)

    def _do_poll(self) -> None:
        controller = self.ctx.controller

        # 阶段 1: controller 还不存在，继续等待
        if controller is None:
            return

        # controller 发生了更换，重置资源重新等待
        if self._controller is not None and self._controller is not controller:
            self._release_resources()

        # 阶段 2: 绑定 controller 并初始化截图控制器
        if self._controller is None:
            if not controller.is_game_window_ready:
                return
            self._controller = controller
            self._screenshot_ctrl = self._create_screenshot_controller()
            if self._screenshot_ctrl is None:
                self._controller = None
                return

        game_win = self._controller.game_win
        if not game_win.is_win_valid:
            return

        # 阶段 3: 前台/后台切换
        if game_win.is_win_active:
            self._dismissed = False
            if self._pip_window is not None and self._pip_window.isVisible():
                if self._worker is not None:
                    self._worker.pause()
                self._pip_window.hide()
        else:
            if self._dismissed:
                return
            if self._pip_window is None:
                self._pip_window, self._worker = self._create_pip_and_worker()
            if self._pip_window is not None and not self._pip_window.isVisible():
                if self._worker is not None:
                    self._worker.resume()
                self._pip_window.show()

    def _create_screenshot_controller(self) -> PcScreenshotController | None:
        c = self._controller
        ctrl = PcScreenshotController(c.game_win, c.standard_width, c.standard_height)
        if ctrl.init_screenshot(c.screenshot_method) is None:
            log.warning('画中画截图器初始化失败')
            return None
        return ctrl

    def _create_pip_and_worker(self) -> tuple[PipWindow | None, PipCaptureWorker | None]:
        """创建画中画窗口和截图线程。"""
        if self._screenshot_ctrl is None:
            return None, None

        screenshot_ctrl = self._screenshot_ctrl
        game_win = self._controller.game_win

        def capture() -> MatLike | None:
            if game_win.win_rect is None:
                return None
            return screenshot_ctrl.get_screenshot(resize=False)

        pip = PipWindow(self.ctx.pip_config)
        worker = PipCaptureWorker(capture)
        worker.frame_ready.connect(pip.on_frame_ready)
        worker.start()

        pip.clicked.connect(self._on_pip_clicked)
        pip.closed.connect(self._on_pip_closed)
        return pip, worker

    def _on_pip_clicked(self) -> None:
        self._controller.game_win.active()

    def _on_pip_closed(self) -> None:
        """用户右键关闭画中画窗口，暂停截图等待游戏切前台后重置。"""
        self._dismissed = True
        if self._worker is not None:
            self._worker.pause()
