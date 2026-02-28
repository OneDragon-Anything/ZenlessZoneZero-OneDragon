from __future__ import annotations

from typing import Sequence

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPen, QResizeEvent
from PySide6.QtWidgets import QWidget

from one_dragon.base.operation.overlay_debug_bus import VisionDrawItem
from one_dragon_qt.overlay.panels.log_panel import LogPanel
from one_dragon_qt.overlay.panels.state_panel import StatePanel
from one_dragon_qt.overlay.utils import win32_utils


_VISION_SOURCE_COLOR = {
    "ocr": "#ff4fa3",
    "template": "#ffd166",
    "yolo": "#24d7ff",
    "cv": "#64d98b",
}


class OverlayWindow(QWidget):
    """Top-most transparent overlay window."""

    panel_geometry_changed = Signal(str, dict)

    def __init__(self):
        super().__init__(None)

        self._passthrough_enabled = True
        self._anti_capture_enabled = True
        self._standard_width = 1920
        self._standard_height = 1080
        self._vision_items: list[VisionDrawItem] = []
        self._vision_layer_enabled = True

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

    def set_standard_resolution(self, width: int, height: int) -> None:
        self._standard_width = max(1, int(width))
        self._standard_height = max(1, int(height))

    def set_vision_layer_enabled(self, enabled: bool) -> None:
        self._vision_layer_enabled = bool(enabled)
        self.update()

    def set_vision_items(self, items: Sequence[VisionDrawItem]) -> None:
        if not self._vision_layer_enabled:
            if self._vision_items:
                self._vision_items = []
                self.update()
            return
        self._vision_items = list(items)
        self.update()

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

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        if not self._vision_layer_enabled or not self._vision_items:
            return
        if self.width() <= 0 or self.height() <= 0:
            return

        scale_x = self.width() / float(self._standard_width)
        scale_y = self.height() / float(self._standard_height)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        for item in self._vision_items:
            rect = self._map_rect(item, scale_x, scale_y)
            if rect is None:
                continue

            base_color = QColor(_VISION_SOURCE_COLOR.get(item.source, item.color or "#bdbdbd"))
            if item.color:
                base_color = QColor(item.color)
            if not base_color.isValid():
                base_color = QColor("#bdbdbd")

            pen = QPen(base_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            label = self._format_vision_label(item)
            if not label:
                continue

            text_h = painter.fontMetrics().height() + 4
            text_w = min(rect.width() + 18, painter.fontMetrics().horizontalAdvance(label) + 8)
            text_y = max(0, rect.top() - text_h - 2)
            text_rect = QRect(rect.left(), text_y, max(40, text_w), text_h)

            painter.fillRect(text_rect, QColor(0, 0, 0, 170))
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(
                text_rect.adjusted(4, 1, -4, -1),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

    @staticmethod
    def _format_vision_label(item: VisionDrawItem) -> str:
        label = (item.label or "").strip()
        if len(label) > 42:
            label = label[:39] + "..."
        if item.score is None:
            return label
        return f"{label} {item.score:.2f}".strip()

    @staticmethod
    def _normalize_coords(x1: int, y1: int, x2: int, y2: int) -> tuple[int, int, int, int]:
        nx1 = min(x1, x2)
        ny1 = min(y1, y2)
        nx2 = max(x1, x2)
        ny2 = max(y1, y2)
        return nx1, ny1, nx2, ny2

    def _map_rect(self, item: VisionDrawItem, scale_x: float, scale_y: float) -> QRect | None:
        x1 = int(item.x1 * scale_x)
        y1 = int(item.y1 * scale_y)
        x2 = int(item.x2 * scale_x)
        y2 = int(item.y2 * scale_y)
        x1, y1, x2, y2 = self._normalize_coords(x1, y1, x2, y2)

        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        if w <= 0 or h <= 0:
            return None
        return QRect(x1, y1, w, h)

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
