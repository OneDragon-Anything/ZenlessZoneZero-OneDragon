from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QWidget

from one_dragon_qt.overlay.panels.log_panel import LogPanel
from one_dragon_qt.overlay.panels.state_panel import StatePanel
from one_dragon_qt.overlay.utils import win32_utils


class OverlayWindow(QWidget):
    """Top-most transparent overlay window."""

    panel_geometry_changed = Signal(str, dict)

    def __init__(self):
        super().__init__(None)

        self._passthrough_enabled = True
        self._anti_capture_enabled = True

        self.setWindowTitle("OneDragon Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.log_panel = LogPanel(self)
        self.state_panel = StatePanel(self)

        self.log_panel.geometry_changed.connect(
            lambda g: self.panel_geometry_changed.emit("log_panel", g)
        )
        self.state_panel.geometry_changed.connect(
            lambda g: self.panel_geometry_changed.emit("state_panel", g)
        )

    def set_log_panel_enabled(self, enabled: bool) -> None:
        self.log_panel.setVisible(enabled)

    def set_state_panel_enabled(self, enabled: bool) -> None:
        self.state_panel.setVisible(enabled)

    def set_panel_appearance(self, font_size: int, text_opacity: int, panel_opacity: int) -> None:
        self.log_panel.set_appearance(font_size, text_opacity, panel_opacity)
        self.state_panel.set_appearance(font_size, text_opacity, panel_opacity)

    def set_passthrough(self, enabled: bool) -> None:
        self._passthrough_enabled = enabled
        hwnd = int(self.winId())
        win32_utils.set_window_click_through(hwnd, enabled)

    def set_anti_capture(self, enabled: bool) -> None:
        self._anti_capture_enabled = enabled
        hwnd = int(self.winId())
        win32_utils.set_window_display_affinity(hwnd, enabled)

    def set_overlay_visible(self, visible: bool) -> None:
        if visible:
            if not self.isVisible():
                self.show()
                self.raise_()
            self.set_passthrough(self._passthrough_enabled)
            self.set_anti_capture(self._anti_capture_enabled)
        else:
            if self.isVisible():
                self.hide()

    def apply_panel_geometry(self, panel_name: str, geometry: dict[str, int]) -> None:
        panel = self._panel_by_name(panel_name)
        if panel is None:
            return
        panel.setGeometry(
            int(geometry.get("x", panel.x())),
            int(geometry.get("y", panel.y())),
            int(geometry.get("w", panel.width())),
            int(geometry.get("h", panel.height())),
        )
        self._clamp_panel(panel)

    def panel_geometries(self) -> dict[str, dict[str, int]]:
        return {
            "log_panel": self._panel_geometry(self.log_panel),
            "state_panel": self._panel_geometry(self.state_panel),
        }

    def update_with_game_rect(self, rect) -> None:
        if rect is None:
            return
        width = int(getattr(rect, "width", 0))
        height = int(getattr(rect, "height", 0))
        left = int(getattr(rect, "x1", 0))
        top = int(getattr(rect, "y1", 0))
        if width <= 0 or height <= 0:
            return
        self.setGeometry(QRect(left, top, width, height))
        self._clamp_all_panels()

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._clamp_all_panels()
        super().resizeEvent(event)

    def _panel_by_name(self, panel_name: str):
        if panel_name == "log_panel":
            return self.log_panel
        if panel_name == "state_panel":
            return self.state_panel
        return None

    @staticmethod
    def _panel_geometry(panel) -> dict[str, int]:
        g = panel.geometry()
        return {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()}

    def _clamp_all_panels(self) -> None:
        self._clamp_panel(self.log_panel)
        self._clamp_panel(self.state_panel)

    def _clamp_panel(self, panel) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return

        g = panel.geometry()
        w = min(max(g.width(), panel.minimumWidth()), self.width())
        h = min(max(g.height(), panel.minimumHeight()), self.height())
        x = g.x()
        y = g.y()

        max_x = max(0, self.width() - w)
        max_y = max(0, self.height() - h)
        x = max(0, min(x, max_x))
        y = max(0, min(y, max_y))

        panel.setGeometry(x, y, w, h)
