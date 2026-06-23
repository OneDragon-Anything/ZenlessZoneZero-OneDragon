import contextlib
import threading
import time

import win32api
import win32gui

from one_dragon.base.controller.pc_game_window import PcGameWindow


class WindowAnchorTracker:

    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    LWA_ALPHA = 0x00000002
    SW_SHOWNOACTIVATE = 4

    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int) -> None:
        self.game_win: PcGameWindow = game_win
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height

        self._running: bool = False
        self._lock: threading.Lock = threading.Lock()
        self._paused: threading.Event = threading.Event()
        self._paused.set()
        self._thread: threading.Thread | None = None
        self._tracker_client_anchor: tuple[int, int] = (self.standard_width // 2, self.standard_height // 2)
        self.settle_time: float = 0.06

    @property
    def running(self) -> bool:
        return self._running

    def _get_default_anchor(self) -> tuple[int, int]:
        rect = self.game_win.win_rect
        if rect is None:
            return self.standard_width // 2, self.standard_height // 2
        return rect.width // 2, rect.height // 2

    def set_anchor(self, anchor: tuple[int, int]) -> None:
        with self._lock:
            self._tracker_client_anchor = anchor

    def reset_anchor(self) -> None:
        self.set_anchor(self._get_default_anchor())

    def get_anchor(self) -> tuple[int, int]:
        with self._lock:
            return self._tracker_client_anchor

    def ensure_ready(self) -> bool:
        if not self._running:
            self.start()
        if not self._running:
            return False
        self._paused.set()
        return True

    def is_pseudo_minimized(self, hwnd: int) -> bool:
        ex_style = win32gui.GetWindowLong(hwnd, self.GWL_EXSTYLE)
        return (ex_style & self.WS_EX_TRANSPARENT) != 0

    def apply_pseudo_minimize(self, hwnd: int) -> None:
        if self.is_pseudo_minimized(hwnd):
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, self.SW_SHOWNOACTIVATE)
            return

        ex_style = win32gui.GetWindowLong(hwnd, self.GWL_EXSTYLE)
        win32gui.SetWindowLong(
            hwnd,
            self.GWL_EXSTYLE,
            ex_style | self.WS_EX_LAYERED | self.WS_EX_TRANSPARENT,
        )
        win32gui.SetLayeredWindowAttributes(hwnd, 0, 0, self.LWA_ALPHA)
        win32gui.ShowWindow(hwnd, self.SW_SHOWNOACTIVATE)

    def revert_pseudo_minimize(self, hwnd: int) -> None:
        if not self.is_pseudo_minimized(hwnd):
            return

        ex_style = win32gui.GetWindowLong(hwnd, self.GWL_EXSTYLE)
        ex_style |= self.WS_EX_LAYERED
        ex_style &= ~self.WS_EX_TRANSPARENT

        win32gui.SetWindowLong(hwnd, self.GWL_EXSTYLE, ex_style)
        win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, self.LWA_ALPHA)

    def _move_window_client_to_cursor(self, hwnd: int, cx: int, cy: int, cursor_x: int, cursor_y: int) -> None:
        if win32gui.IsIconic(hwnd):
            self.apply_pseudo_minimize(hwnd)

        win_rect = win32gui.GetWindowRect(hwnd)
        client_origin = win32gui.ClientToScreen(hwnd, (0, 0))
        border_left = client_origin[0] - win_rect[0]
        border_top = client_origin[1] - win_rect[1]

        new_x = cursor_x - cx - border_left
        new_y = cursor_y - cy - border_top

        win32gui.SetWindowPos(
            hwnd, 0, new_x, new_y, 0, 0,
            self.SWP_NOSIZE | self.SWP_NOZORDER | self.SWP_NOACTIVATE,
        )

    def _align_anchor_to_cursor(self, hwnd: int) -> None:
        cursor_x, cursor_y = win32api.GetCursorPos()
        ax, ay = self.get_anchor()
        self._move_window_client_to_cursor(hwnd, ax, ay, cursor_x, cursor_y)

    def start(self) -> None:
        if self._running:
            return

        self.reset_anchor()
        self._running = True
        self._paused.set()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='aggressive_bg_tracker')
        self._thread.start()

        hwnd = self.game_win.get_hwnd()
        if hwnd:
            with contextlib.suppress(Exception):
                self.apply_pseudo_minimize(hwnd)

    def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        self._paused.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

        hwnd = self.game_win.get_hwnd()
        if hwnd:
            deadline = time.time() + 0.2
            while True:
                if win32gui.IsIconic(hwnd):
                    with contextlib.suppress(Exception):
                        win32gui.ShowWindow(hwnd, self.SW_SHOWNOACTIVATE)
                with contextlib.suppress(Exception):
                    self.revert_pseudo_minimize(hwnd)
                if not win32gui.IsIconic(hwnd) and not self.is_pseudo_minimized(hwnd):
                    break
                if time.time() >= deadline:
                    break
                time.sleep(0.02)

            with contextlib.suppress(Exception):
                rect = win32gui.GetWindowRect(hwnd)
                win_w = rect[2] - rect[0]
                win_h = rect[3] - rect[1]
                screen_w = win32api.GetSystemMetrics(0)
                screen_h = win32api.GetSystemMetrics(1)
                center_x = max((screen_w - win_w) // 2, 0)
                center_y = max((screen_h - win_h) // 2, 0)
                win32gui.SetWindowPos(
                    hwnd, 0,
                    center_x, center_y, 0, 0,
                    self.SWP_NOSIZE | self.SWP_NOZORDER | self.SWP_NOACTIVATE,
                )

    def _loop(self) -> None:
        while self._running:
            self._paused.wait()
            if not self._running:
                break
            try:
                hwnd = self.game_win.get_hwnd()
                if hwnd:
                    if win32gui.GetForegroundWindow() != hwnd or win32gui.IsIconic(hwnd):
                        self.apply_pseudo_minimize(hwnd)
                    self._align_anchor_to_cursor(hwnd)
            except Exception:
                pass
            time.sleep(0.016)
