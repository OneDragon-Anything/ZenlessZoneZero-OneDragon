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
from one_dragon_qt.overlay.panels.info_hud_panel import InfoHudPanel
from one_dragon_qt.overlay.utils import win32_utils


_VISION_SOURCE_COLOR = {
    "ocr": "#ff4fa3",
    "template": "#ffd166",
    "yolo": "#24d7ff",
    "cv": "#64d98b",
}


class OverlayWindow(QWidget):
    """Top-most transparent overlay window.

    Contains only the vision-draw paint layer and an InfoHudPanel
    (Afterburner-style OSD).  The LogPanel is now managed externally as
    an independent top-level window by OverlayManager.
    """

    panel_geometry_changed = Signal(str, dict)

    def __init__(self):
        super().__init__(None)

        self._passthrough_enabled = True
        self._anti_capture_enabled = True
        self._standard_width = 1920
        self._standard_height = 1080
        self._vision_items: list[VisionDrawItem] = []
        self._vision_layer_enabled = True
        self._vision_offset_x = 0
        self._vision_offset_y = 0
        self._vision_scale_x = 1.0
        self._vision_scale_y = 1.0

        self.setWindowTitle("OneDragon Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # InfoHudPanel replaces the old state/decision/timeline/performance panels
        self.info_hud_panel = InfoHudPanel(self)

    def set_info_hud_enabled(self, enabled: bool) -> None:
        self.info_hud_panel.setVisible(enabled)

    def set_panel_appearance(self, font_size: int, text_opacity: int, panel_opacity: int) -> None:
        self.info_hud_panel.set_appearance(font_size, text_opacity, panel_opacity)

    def set_standard_resolution(self, width: int, height: int) -> None:
        self._standard_width = max(1, int(width))
        self._standard_height = max(1, int(height))

    def set_vision_layer_enabled(self, enabled: bool) -> None:
        self._vision_layer_enabled = bool(enabled)
        self.update()

    def set_vision_transform(
        self,
        offset_x: int = 0,
        offset_y: int = 0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
    ) -> None:
        self._vision_offset_x = int(offset_x)
        self._vision_offset_y = int(offset_y)
        self._vision_scale_x = max(0.5, min(1.5, float(scale_x)))
        self._vision_scale_y = max(0.5, min(1.5, float(scale_y)))
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
        self.info_hud_panel.update_decisions(list(items))

    def set_timeline_items(self, items: Sequence[TimelineItem]) -> None:
        self.info_hud_panel.update_timeline(list(items))

    def set_performance_items(self, items: Sequence[PerfMetricSample]) -> None:
        self.info_hud_panel.update_performance(list(items))

    def set_performance_metric_enabled_map(self, metric_enabled: dict[str, bool] | None) -> None:
        self.info_hud_panel.set_enabled_metric_map(metric_enabled)

    def update_state_snapshot(self, items: list[tuple[str, str]]) -> None:
        self.info_hud_panel.update_state(items)

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
        """No-op: panels are now either InfoHudPanel (auto-docked) or independent LogPanel."""
        pass

    def panel_geometries(self) -> dict[str, dict[str, int]]:
        return {}

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
        self._dock_info_hud()

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._dock_info_hud()
        super().resizeEvent(event)

    def _dock_info_hud(self) -> None:
        """Position InfoHudPanel at the right edge of the overlay window."""
        if self.width() <= 0 or self.height() <= 0:
            return
        margin = 8
        hud_w = max(200, min(320, int(self.width() * 0.19)))
        hud_h = max(120, min(self.height() - margin * 2, int(self.height() * 0.55)))
        x = max(0, self.width() - margin - hud_w)
        y = margin
        self.info_hud_panel.setGeometry(x, y, hud_w, hud_h)

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
        map_scale_x = scale_x * self._vision_scale_x
        map_scale_y = scale_y * self._vision_scale_y
        x1 = int(item.x1 * map_scale_x) + self._vision_offset_x
        y1 = int(item.y1 * map_scale_y) + self._vision_offset_y
        x2 = int(item.x2 * map_scale_x) + self._vision_offset_x
        y2 = int(item.y2 * map_scale_y) + self._vision_offset_y
        x1, y1, x2, y2 = self._normalize_coords(x1, y1, x2, y2)

        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        if w <= 0 or h <= 0:
            return None
        return QRect(x1, y1, w, h)

    def _panel_by_name(self, panel_name: str):
        return None

    @staticmethod
    def _panel_geometry(panel) -> dict[str, int]:
        g = panel.geometry()
        return {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()}
