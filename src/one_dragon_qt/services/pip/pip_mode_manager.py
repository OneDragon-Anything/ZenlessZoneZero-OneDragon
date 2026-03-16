from __future__ import annotations

from cv2.typing import MatLike
from PySide6.QtCore import QTimer

from one_dragon.base.controller.pc_controller_base import PcControllerBase
from one_dragon.base.controller.pc_screenshot.pc_screenshot_controller import (
    PcScreenshotController,
)
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.pip_window import PipWindow


class PipModeManager:
    """画中画模式管理器

    开启后轮询游戏窗口状态：
    - 游戏切到后台 -> 自动显示画中画
    - 游戏切到前台 -> 自动隐藏画中画
    - 画中画被点击 -> 游戏切到前台
    """

    POLL_INTERVAL_MS: int = 200

    def __init__(self, controller: PcControllerBase) -> None:
        self._controller = controller
        self._pip_window: PipWindow | None = None
        self._screenshot_ctrl: PcScreenshotController | None = None
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._on_poll)
        self._active: bool = False

    @property
    def is_active(self) -> bool:
        return self._active

    def toggle(self) -> bool:
        """切换画中画模式，返回切换后的状态。"""
        if self._active:
            self.stop()
            return False
        return self.start()

    def start(self) -> bool:
        """开启画中画模式。"""
        if self._active:
            return True

        self._screenshot_ctrl = self._create_screenshot_controller()
        if self._screenshot_ctrl is None:
            return False

        self._active = True
        self._poll_timer.start(self.POLL_INTERVAL_MS)
        self._on_poll()
        return True

    def stop(self) -> None:
        """关闭画中画模式，释放所有资源。"""
        self._active = False
        self._poll_timer.stop()
        self._close_pip()
        if self._screenshot_ctrl is not None:
            self._screenshot_ctrl.cleanup()
            self._screenshot_ctrl = None

    def _on_poll(self) -> None:
        """轮询游戏窗口前台状态。"""
        game_win = self._controller.game_win
        if not game_win.is_win_valid:
            return

        if game_win.is_win_active:
            if self._pip_window is not None and self._pip_window.isVisible():
                self._pip_window.hide()
        else:
            if self._pip_window is None:
                self._pip_window = self._create_pip_window()
            if self._pip_window is not None and not self._pip_window.isVisible():
                self._pip_window.show()

    def _create_screenshot_controller(self) -> PcScreenshotController | None:
        c = self._controller
        ctrl = PcScreenshotController(c.game_win, c.standard_width, c.standard_height)
        if ctrl.init_screenshot(c.screenshot_method) is None:
            log.warning('画中画截图器初始化失败')
            return None
        return ctrl

    def _create_pip_window(self) -> PipWindow | None:
        if self._screenshot_ctrl is None:
            return None

        screenshot_ctrl = self._screenshot_ctrl
        game_win = self._controller.game_win

        def capture() -> MatLike | None:
            if game_win.win_rect is None:
                return None
            return screenshot_ctrl.get_screenshot()

        pip = PipWindow(capture_fn=capture)
        pip.clicked.connect(self._on_pip_clicked)
        pip.closed.connect(self._on_pip_closed)
        return pip

    def _on_pip_clicked(self) -> None:
        self._controller.game_win.active()

    def _on_pip_closed(self) -> None:
        self._pip_window = None
        self.stop()

    def _close_pip(self) -> None:
        if self._pip_window is not None:
            self._pip_window.closed.disconnect(self._on_pip_closed)
            self._pip_window.close()
            self._pip_window = None
