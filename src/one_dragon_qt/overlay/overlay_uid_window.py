from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from one_dragon_qt.overlay.utils import win32_utils


class OverlayUidWindow(QWidget):
    """UID 遮挡窗口。

    独立于 OverlayHudWindow，可单独控制防录屏属性 (WDA_NONE / WDA_EXCLUDEFROMCAPTURE)，
    使录屏与推流软件能够捕获遮挡块（与游戏画面同层录制），同时避免暴露 HUD 调试面板。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._anti_capture: bool = False
        self._passthrough_enabled: bool = True
        self._affinity_set: bool = False
        self._passthrough_set: bool = False

        self.setWindowTitle("OneDragon UID Mask")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#727272"))

    def set_passthrough(self, enabled: bool) -> None:
        if self._passthrough_enabled == enabled and self._passthrough_set:
            return
        self._passthrough_enabled = enabled
        if self.isVisible():
            hwnd = int(self.winId())
            self._passthrough_set = win32_utils.set_window_click_through(hwnd, enabled)

    def set_anti_capture(self, enabled: bool) -> None:
        if self._anti_capture == enabled and self._affinity_set:
            return
        self._anti_capture = enabled
        if self.isVisible():
            hwnd = int(self.winId())
            self._affinity_set = win32_utils.set_window_display_affinity(hwnd, enabled)

    def set_mask_visible(self, visible: bool) -> None:
        if visible:
            if not self.isVisible():
                self.show()
                self.raise_()
                self._passthrough_set = False
                self._affinity_set = False
            self.set_passthrough(self._passthrough_enabled)
            self.set_anti_capture(self._anti_capture)
        else:
            if self.isVisible():
                self.hide()
