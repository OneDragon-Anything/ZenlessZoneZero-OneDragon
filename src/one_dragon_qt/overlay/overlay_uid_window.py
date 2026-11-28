from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from one_dragon_qt.overlay.utils import win32_utils


class OverlayUidWindow(QWidget):
    """UID 遮挡窗口。

    独立于 OverlayHudWindow，不设置防截图属性（始终保持 WDA_NONE），
    使桌面录屏与外部截图工具能够捕获遮挡块，同时避免触发受保护内容标记。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._passthrough_enabled: bool = True
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

    def set_mask_visible(self, visible: bool) -> None:
        if visible:
            if not self.isVisible():
                self.show()
                self.raise_()
                self._passthrough_set = False
            self.set_passthrough(self._passthrough_enabled)
        else:
            if self.isVisible():
                self.hide()
