from __future__ import annotations

from typing import Sequence

import numpy as np
from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPaintEvent, QPainter, QPen, QResizeEvent
from PySide6.QtWidgets import QWidget

from one_dragon.base.operation.overlay_debug_bus import (
    DecisionTraceItem,
    PerfMetricSample,
    TimelineItem,
    VisionDrawItem,
)
from one_dragon_qt.overlay.panels.decision_panel import DecisionPanel
from one_dragon_qt.overlay.panels.log_panel import LogPanel
from one_dragon_qt.overlay.panels.performance_panel import PerformancePanel
from one_dragon_qt.overlay.panels.state_panel import StatePanel
from one_dragon_qt.overlay.panels.timeline_panel import TimelinePanel
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
        self.decision_panel = DecisionPanel(self)
        self.timeline_panel = TimelinePanel(self)
        self.performance_panel = PerformancePanel(self)
        self._side_panels_docked = True

        # Keep log panel draggable; side panels are docked.
        self.log_panel.set_interaction_enabled(True)
        self.state_panel.set_interaction_enabled(False)
        self.decision_panel.set_interaction_enabled(False)
        self.timeline_panel.set_interaction_enabled(False)
        self.performance_panel.set_interaction_enabled(False)

        self.log_panel.geometry_changed.connect(
            lambda g: self.panel_geometry_changed.emit("log_panel", g)
        )
        self.state_panel.geometry_changed.connect(
            lambda g: self.panel_geometry_changed.emit("state_panel", g)
        )
        self.decision_panel.geometry_changed.connect(
            lambda g: self.panel_geometry_changed.emit("decision_panel", g)
        )
        self.timeline_panel.geometry_changed.connect(
            lambda g: self.panel_geometry_changed.emit("timeline_panel", g)
        )
        self.performance_panel.geometry_changed.connect(
            lambda g: self.panel_geometry_changed.emit("performance_panel", g)
        )

    def set_log_panel_enabled(self, enabled: bool) -> None:
        self.log_panel.setVisible(enabled)

    def set_state_panel_enabled(self, enabled: bool) -> None:
        self.state_panel.setVisible(enabled)
        if self._side_panels_docked:
            self.dock_side_panels()

    def set_decision_panel_enabled(self, enabled: bool) -> None:
        self.decision_panel.setVisible(enabled)
        if self._side_panels_docked:
            self.dock_side_panels()

    def set_timeline_panel_enabled(self, enabled: bool) -> None:
        self.timeline_panel.setVisible(enabled)
        if self._side_panels_docked:
            self.dock_side_panels()

    def set_performance_panel_enabled(self, enabled: bool) -> None:
        self.performance_panel.setVisible(enabled)
        if self._side_panels_docked:
            self.dock_side_panels()

    def set_side_panels_docked(self, docked: bool) -> None:
        self._side_panels_docked = bool(docked)
        enabled = not self._side_panels_docked
        self.state_panel.set_interaction_enabled(enabled)
        self.decision_panel.set_interaction_enabled(enabled)
        self.timeline_panel.set_interaction_enabled(enabled)
        self.performance_panel.set_interaction_enabled(enabled)
        if self._side_panels_docked:
            self.dock_side_panels()

    def set_panel_appearance(self, font_size: int, text_opacity: int, panel_opacity: int) -> None:
        self.log_panel.set_appearance(font_size, text_opacity, panel_opacity)
        self.state_panel.set_appearance(font_size, text_opacity, panel_opacity)
        self.decision_panel.set_appearance(font_size, text_opacity, panel_opacity)
        self.timeline_panel.set_appearance(font_size, text_opacity, panel_opacity)
        self.performance_panel.set_appearance(font_size, text_opacity, panel_opacity)

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

    def set_decision_items(self, items: Sequence[DecisionTraceItem]) -> None:
        self.decision_panel.update_items(list(items))

    def set_timeline_items(self, items: Sequence[TimelineItem]) -> None:
        self.timeline_panel.update_items(list(items))

    def set_performance_items(self, items: Sequence[PerfMetricSample]) -> None:
        self.performance_panel.update_items(list(items))

    def set_performance_metric_enabled_map(self, metric_enabled: dict[str, bool] | None) -> None:
        self.performance_panel.set_enabled_metric_map(metric_enabled)

    def capture_overlay_rgba(self) -> np.ndarray | None:
        if not self.isVisible() or self.width() <= 0 or self.height() <= 0:
            return None

        pixmap = self.grab()
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        width = image.width()
        height = image.height()
        if width <= 0 or height <= 0:
            return None

        buffer = image.bits()
        arr = np.frombuffer(
            buffer,
            dtype=np.uint8,
            count=image.bytesPerLine() * height,
        ).reshape((height, image.bytesPerLine() // 4, 4))
        return arr[:, :width, :].copy()

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
            "decision_panel": self._panel_geometry(self.decision_panel),
            "timeline_panel": self._panel_geometry(self.timeline_panel),
            "performance_panel": self._panel_geometry(self.performance_panel),
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
        if self._side_panels_docked:
            self.dock_side_panels()
        self._clamp_all_panels()

    def resizeEvent(self, event: QResizeEvent) -> None:
        if self._side_panels_docked:
            self.dock_side_panels()
        self._clamp_all_panels()
        super().resizeEvent(event)

    def dock_side_panels(self) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return

        ordered = [
            ("state_panel", self.state_panel, 120),
            ("decision_panel", self.decision_panel, 140),
            ("timeline_panel", self.timeline_panel, 170),
            ("performance_panel", self.performance_panel, 110),
        ]
        visible_items = [(name, panel, h) for name, panel, h in ordered if panel.isVisible()]
        if not visible_items:
            return

        margin = 10
        gap = 6
        side_w = max(200, min(300, int(self.width() * 0.18)))
        x = max(0, self.width() - margin - side_w)

        base_height_sum = sum(base_h for _, _, base_h in visible_items)
        available_h = max(80, self.height() - margin * 2 - gap * (len(visible_items) - 1))
        if available_h >= base_height_sum:
            heights = [base_h for _, _, base_h in visible_items]
        else:
            panel_count = len(visible_items)
            min_h = max(8, min(24, available_h // max(1, panel_count)))
            heights = [
                max(min_h, int(available_h * (base_h / float(max(1, base_height_sum)))))
                for _, _, base_h in visible_items
            ]
            total_h = sum(heights)
            if total_h > available_h:
                overflow = total_h - available_h
                for idx in range(len(heights) - 1, -1, -1):
                    reducible = heights[idx] - min_h
                    if reducible <= 0:
                        continue
                    delta = min(reducible, overflow)
                    heights[idx] -= delta
                    overflow -= delta
                    if overflow <= 0:
                        break

        y = margin
        for idx, (_, panel, _) in enumerate(visible_items):
            h = max(8, heights[idx])
            panel.setGeometry(x, y, side_w, h)
            y += h + gap

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
        if panel_name == "decision_panel":
            return self.decision_panel
        if panel_name == "timeline_panel":
            return self.timeline_panel
        if panel_name == "performance_panel":
            return self.performance_panel
        return None

    @staticmethod
    def _panel_geometry(panel) -> dict[str, int]:
        g = panel.geometry()
        return {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()}

    def _clamp_all_panels(self) -> None:
        self._clamp_panel(self.log_panel)
        self._clamp_panel(self.state_panel)
        self._clamp_panel(self.decision_panel)
        self._clamp_panel(self.timeline_panel)
        self._clamp_panel(self.performance_panel)

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
