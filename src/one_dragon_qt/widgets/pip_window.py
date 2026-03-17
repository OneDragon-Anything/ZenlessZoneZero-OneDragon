from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QWidget

from one_dragon.base.config.pip_config import PipConfig


class PipWindow(QWidget):
    """画中画窗口 - 始终置顶的无边框半透明截图预览窗口

    纯显示组件：接收 numpy 帧并绘制。宽度可缩放，高度由帧比例决定。
    左键单击发出 clicked 信号，左键拖拽移动，边缘拖拽缩放，右键关闭。
    窗口尺寸和位置通过 PipConfig 持久化。
    """

    clicked = Signal()
    closed = Signal()

    BORDER_WIDTH: int = 1
    CORNER_RADIUS_RATIO: float = 0.03
    EDGE_ZONE: int = 8
    DRAG_THRESHOLD: int = 5
    MIN_WIDTH: int = 320
    MAX_WIDTH: int = 1920

    def __init__(self, config: PipConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._config = config
        self._frame: QPixmap | None = None
        self._aspect_ratio: float = 9 / 16  # h/w，默认 16:9，收到第一帧后更新

        # 拖拽状态
        self._dragging: bool = False
        self._drag_start_pos: QPoint | None = None
        self._press_global_pos: QPoint | None = None

        # 缩放状态
        self._resizing: bool = False
        self._resize_edge: str = ''
        self._resize_start_rect: QRect | None = None
        self._resize_start_mouse: QPoint | None = None

        # 右键关闭
        self._right_pressed: bool = False

        # 从 config 恢复尺寸
        w = max(self.MIN_WIDTH, min(self.MAX_WIDTH, config.width))
        h = int(w * self._aspect_ratio)
        self.resize(w, h)

        self.setMouseTracking(True)

        # 从 config 恢复位置
        if config.x >= 0 and config.y >= 0:
            self.move(config.x, config.y)
        else:
            self._move_to_bottom_right()

    # ------------------------------------------------------------------
    # 帧更新 (由外部 Worker signal 调用)
    # ------------------------------------------------------------------

    def on_frame_ready(self, frame: np.ndarray) -> None:
        h, w = frame.shape[:2]
        if h <= 0 or w <= 0:
            return

        # 更新比例，根据宽度计算高度
        self._aspect_ratio = h / w
        new_h = int(self.width() * self._aspect_ratio)
        if self.height() != new_h:
            self.resize(self.width(), new_h)

        # numpy -> QImage -> QPixmap
        if frame.ndim == 3 and frame.shape[2] == 3:
            bytes_per_line = 3 * w
            q_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            self._frame = QPixmap.fromImage(q_image.copy())
        else:
            return
        self.update()

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        b = self.BORDER_WIDTH
        rect = self.rect()
        radius = min(rect.width(), rect.height()) * self.CORNER_RADIUS_RATIO
        inner_radius = max(0, radius - b)

        # 内容区：用边框内边缘的圆角裁剪
        content_rect = QRectF(rect.adjusted(b, b, -b, -b))
        clip_path = QPainterPath()
        clip_path.addRoundedRect(content_rect, inner_radius, inner_radius)
        painter.setClipPath(clip_path)

        if self._frame is not None:
            painter.drawPixmap(content_rect.toRect(), self._frame)
        else:
            painter.fillRect(content_rect, QColor(0, 0, 0, 200))

        # 半透明边框（在内容之上绘制）
        painter.setClipping(False)
        border_color = QColor(83, 83, 83, 144)
        painter.setPen(QPen(border_color, b))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        half = b / 2
        border_rect = QRectF(half, half, rect.width() - b, rect.height() - b)
        painter.drawRoundedRect(border_rect, radius, radius)

        painter.end()

    # ------------------------------------------------------------------
    # 鼠标交互
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._right_pressed = True
            return

        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._detect_edge(event.pos())
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._resize_start_rect = self.geometry()
                self._resize_start_mouse = event.globalPosition().toPoint()
            else:
                self._press_global_pos = event.globalPosition().toPoint()
                self._drag_start_pos = self._press_global_pos - self.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_global_pos is not None and self._drag_start_pos is not None:
            delta = event.globalPosition().toPoint() - self._press_global_pos
            if self._dragging or (abs(delta.x()) + abs(delta.y()) > self.DRAG_THRESHOLD):
                self._dragging = True
                self.move(event.globalPosition().toPoint() - self._drag_start_pos)
        elif self._resizing:
            self._do_resize(event.globalPosition().toPoint())
        else:
            edge = self._detect_edge(event.pos())
            if edge:
                self.setCursor(self._edge_to_cursor(edge))
            else:
                self.unsetCursor()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton and self._right_pressed:
            self._right_pressed = False
            self._save_geometry()
            self.hide()
            self.closed.emit()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if not self._dragging and not self._resizing and self._press_global_pos is not None:
                self.clicked.emit()

        if self._dragging or self._resizing:
            self._save_geometry()

        self._dragging = False
        self._resizing = False
        self._drag_start_pos = None
        self._press_global_pos = None
        self._resize_edge = ''
        self._resize_start_rect = None
        self._resize_start_mouse = None

    # ------------------------------------------------------------------
    # 边缘检测与缩放
    # ------------------------------------------------------------------

    def _detect_edge(self, pos: QPoint) -> str:
        e = self.EDGE_ZONE
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()

        edge = ''
        if y < e:
            edge += 't'
        if y > h - e:
            edge += 'b'
        if x < e:
            edge += 'l'
        if x > w - e:
            edge += 'r'
        return edge

    @staticmethod
    def _edge_to_cursor(edge: str) -> Qt.CursorShape:
        mapping = {
            'r': Qt.CursorShape.SizeHorCursor,
            'l': Qt.CursorShape.SizeHorCursor,
            'b': Qt.CursorShape.SizeVerCursor,
            't': Qt.CursorShape.SizeVerCursor,
            'rb': Qt.CursorShape.SizeFDiagCursor,
            'br': Qt.CursorShape.SizeFDiagCursor,
            'lt': Qt.CursorShape.SizeFDiagCursor,
            'tl': Qt.CursorShape.SizeFDiagCursor,
            'rt': Qt.CursorShape.SizeBDiagCursor,
            'tr': Qt.CursorShape.SizeBDiagCursor,
            'lb': Qt.CursorShape.SizeBDiagCursor,
            'bl': Qt.CursorShape.SizeBDiagCursor,
        }
        return mapping.get(edge, Qt.CursorShape.ArrowCursor)

    def _do_resize(self, global_pos: QPoint) -> None:
        if self._resize_start_rect is None or self._resize_start_mouse is None:
            return

        dx = global_pos.x() - self._resize_start_mouse.x()
        dy = global_pos.y() - self._resize_start_mouse.y()
        r = self._resize_start_rect
        edge = self._resize_edge

        new_w = r.width()

        if 'r' in edge:
            new_w = r.width() + dx
        elif 'l' in edge:
            new_w = r.width() - dx

        # 如果只有纵向拖拽，按比例反推宽度
        if ('r' not in edge and 'l' not in edge) and ('b' in edge or 't' in edge):
            new_h = r.height() + dy if 'b' in edge else r.height() - dy
            if self._aspect_ratio > 0:
                new_w = int(new_h / self._aspect_ratio)

        new_w = max(self.MIN_WIDTH, min(self.MAX_WIDTH, new_w))
        new_h = int(new_w * self._aspect_ratio)

        new_x = r.right() - new_w + 1 if 'l' in edge else r.x()
        new_y = r.bottom() - new_h + 1 if 't' in edge else r.y()

        self.setGeometry(new_x, new_y, new_w, new_h)
        self._save_geometry()

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _move_to_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        margin = 20
        self.move(geo.right() - self.width() - margin, geo.bottom() - self.height() - margin)

    def _save_geometry(self) -> None:
        """保存当前窗口宽度和位置到 config。"""
        self._config.width = self.width()
        self._config.x = self.x()
        self._config.y = self.y()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_geometry()
        self.closed.emit()
        super().closeEvent(event)
