from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from one_dragon.base.operation.overlay_debug_bus import VisionDrawItem
from one_dragon_qt.overlay.utils import win32_utils

_VISION_SOURCE_COLOR = {
    "ocr": "#ff4fa3",
    "template": "#ffd166",
    "yolo": "#24d7ff",
    "cv": "#64d98b",
}


class OverlayWindow(QWidget):
    """Top-most transparent overlay window.

    只负责 vision 检测框绘制层；信息面板已迁移到 Qt Quick (overlay_hud.qml)。
    """

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

            # 光晕色 = 来源色（ocr 粉 / template 橙 / yolo 青 / cv 绿），主体白色描边
            glow_color = QColor(_VISION_SOURCE_COLOR.get(item.source, item.color or "#bdbdbd"))
            if item.color:
                glow_color = QColor(item.color)
            if not glow_color.isValid():
                glow_color = QColor("#bdbdbd")

            radius = 8
            path = QPainterPath()
            path.addRoundedRect(rect, radius, radius)

            # 外发光：多层平滑渐隐（最外层超宽超淡做羽化，光晕末端化开，无硬环边）
            glow_layers = (
                (17, 14),
                (13, 30),
                (9, 60),
                (5, 110),
                (2, 170),
            )
            for glow_w, glow_alpha in glow_layers:
                gc = QColor(glow_color)
                gc.setAlpha(glow_alpha)
                gp = QPen(gc)
                gp.setWidth(glow_w)
                gp.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(gp)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            # 主框：白色圆角细线
            pen = QPen(QColor(255, 255, 255))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

            label = self._format_vision_label(item)
            if not label:
                continue

            text_h = painter.fontMetrics().height() + 4
            # 背景框宽度按完整文本宽度自适应，不裁剪模板名
            text_w = painter.fontMetrics().horizontalAdvance(label) + 12

            # 标签放在朝向屏幕中心的一侧（框在上半放下面、下半放上面、左半放右边、右半放左边）
            # 取偏移更大的轴定方向，并 clamp 到窗口内，避免边缘出屏
            gap = 4
            box_c = rect.center()
            screen_c = QPoint(self.width() // 2, self.height() // 2)
            if abs(box_c.x() - screen_c.x()) >= abs(box_c.y() - screen_c.y()):
                x = rect.right() + gap if box_c.x() < screen_c.x() else rect.left() - text_w - gap
                y = box_c.y() - text_h // 2
                x = max(2, min(x, self.width() - text_w - 2))
                y = max(2, min(y, self.height() - text_h - 2))
            else:
                y = rect.bottom() + gap if box_c.y() < screen_c.y() else rect.top() - text_h - gap
                x = box_c.x() - text_w // 2
                y = max(2, min(y, self.height() - text_h - 2))
                x = max(2, min(x, self.width() - text_w - 2))
            text_rect = QRect(x, y, text_w, text_h)

            painter.fillRect(text_rect, QColor(0, 0, 0, 205))
            label_font = painter.font()
            label_font.setBold(True)
            painter.setFont(label_font)
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(
                text_rect.adjusted(4, 1, -4, -1),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

    @staticmethod
    def _format_vision_label(item: VisionDrawItem) -> str:
        label = (item.label or "").strip()
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
        return QRect(x1, y1, w, h)
