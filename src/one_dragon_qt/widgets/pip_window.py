from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
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
    QWheelEvent,
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
    WHEEL_STEP: int = 40
    MIN_WIDTH: int = 320
    MAX_WIDTH: int = 1920
    CLOSE_BTN_SIZE: int = 32
    CLOSE_BTN_MARGIN: int = 8
    CLOSE_ICON_SIZE: int = 8

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

        # 关闭按钮状态
        self._close_hovered: bool = False
        self._close_visible: bool = False

        # 从 config 恢复尺寸（config.width 是内容宽度，不含边框）
        b2 = self.BORDER_WIDTH * 2
        cw = max(self.MIN_WIDTH, min(self.MAX_WIDTH, config.width))
        self.resize(cw + b2, self._height_for_width(cw))

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
        content_w = self.width() - self.BORDER_WIDTH * 2
        new_win_h = self._height_for_width(content_w)
        if self.height() != new_win_h:
            self.resize(self.width(), new_win_h)

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

        # 内容区：边框内侧的圆角区域
        content_rect = QRectF(rect.adjusted(b, b, -b, -b))
        clip_path = QPainterPath()
        clip_path.addRoundedRect(content_rect, inner_radius, inner_radius)
        painter.setClipPath(clip_path)

        if self._frame is not None:
            painter.drawPixmap(content_rect.toRect(), self._frame)
        else:
            painter.fillRect(content_rect, QColor(0, 0, 0, 200))

        # 边框：画在窗口最外圈，包裹内容
        painter.setClipping(False)
        border_color = QColor(83, 83, 83, 144)
        painter.setPen(QPen(border_color, b))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        half = b / 2
        border_rect = QRectF(half, half, rect.width() - b, rect.height() - b)
        painter.drawRoundedRect(border_rect, radius, radius)

        # 关闭按钮（鼠标在窗体内时显示）
        if self._close_visible:
            btn = self._close_btn_rect()
            btn_f = QRectF(btn)
            cx = btn_f.center().x()
            cy = btn_f.center().y()
            icon_half = self.CLOSE_ICON_SIZE / 2

            # 半透明深色背景（悬停时更深）
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 80 if self._close_hovered else 20))
            painter.drawRoundedRect(btn_f, 4, 4)

            # 白色 X
            p1 = QPointF(cx - icon_half, cy - icon_half)
            p2 = QPointF(cx + icon_half, cy + icon_half)
            p3 = QPointF(cx + icon_half, cy - icon_half)
            p4 = QPointF(cx - icon_half, cy + icon_half)
            painter.setPen(QPen(QColor(255, 255, 255, 220), 1.5))
            painter.drawLine(p1, p2)
            painter.drawLine(p3, p4)

        painter.end()

    # ------------------------------------------------------------------
    # 鼠标交互
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._right_pressed = True
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self._close_btn_rect().contains(event.pos()):
                self._save_geometry()
                self.hide()
                self.closed.emit()
                return

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
            hovered = self._close_btn_rect().contains(event.pos())
            need_update = False
            if not self._close_visible:
                self._close_visible = True
                need_update = True
            if hovered != self._close_hovered:
                self._close_hovered = hovered
                need_update = True
            if need_update:
                self.update()
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

    def leaveEvent(self, event) -> None:
        if self._close_hovered or self._close_visible:
            self._close_hovered = False
            self._close_visible = False
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return

        step = self.WHEEL_STEP if delta > 0 else -self.WHEEL_STEP
        b2 = self.BORDER_WIDTH * 2
        old_w, old_h = self.width(), self.height()
        old_cw = old_w - b2
        new_cw = max(self.MIN_WIDTH, min(self.MAX_WIDTH, old_cw + step))
        if new_cw == old_cw:
            return

        new_w = new_cw + b2
        new_h = self._height_for_width(new_cw)

        # 锚点缩放：鼠标在窗口中指向的内容点在屏幕上的位置不变
        mouse_pos = event.position()
        # 鼠标在内容中的相对位置
        content_rx = (mouse_pos.x() - self.BORDER_WIDTH) / old_cw
        content_ry = (mouse_pos.y() - self.BORDER_WIDTH) / (old_h - b2)
        # 缩放后鼠标应在窗口中的新位置
        new_mouse_x = content_rx * new_cw + self.BORDER_WIDTH
        new_mouse_y = content_ry * (new_h - b2) + self.BORDER_WIDTH
        # 窗口左上角偏移，使屏幕上鼠标位置不动
        new_x = round(self.x() + mouse_pos.x() - new_mouse_x)
        new_y = round(self.y() + mouse_pos.y() - new_mouse_y)

        self.setGeometry(new_x, new_y, new_w, new_h)
        self._save_geometry()

    # ------------------------------------------------------------------
    # 边缘检测与缩放
    # ------------------------------------------------------------------

    def _close_btn_rect(self) -> QRect:
        s = self.CLOSE_BTN_SIZE
        m = self.CLOSE_BTN_MARGIN
        return QRect(self.width() - s - m, m, s, s)

    def _detect_edge(self, pos: QPoint) -> str:
        e = self.EDGE_ZONE
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()

        edge = ''
        if y < e:
            edge += 't'
        if y >= h - e:
            edge += 'b'
        if x < e:
            edge += 'l'
        if x >= w - e:
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
        b2 = self.BORDER_WIDTH * 2

        new_cw = r.width() - b2  # 初始内容宽度

        if 'r' in edge:
            new_cw = r.width() - b2 + dx
        elif 'l' in edge:
            new_cw = r.width() - b2 - dx

        # 如果只有纵向拖拽，按比例反推内容宽度
        if ('r' not in edge and 'l' not in edge) and ('b' in edge or 't' in edge):
            new_h = r.height() + dy if 'b' in edge else r.height() - dy
            if self._aspect_ratio > 0:
                new_cw = int((new_h - b2) / self._aspect_ratio)

        new_cw = max(self.MIN_WIDTH, min(self.MAX_WIDTH, new_cw))
        new_w = new_cw + b2
        new_h = self._height_for_width(new_cw)

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

    def _height_for_width(self, content_w: int) -> int:
        """根据内容宽度和帧比例，计算对应的窗口高度（含边框）。"""
        return int(content_w * self._aspect_ratio) + self.BORDER_WIDTH * 2

    def _save_geometry(self) -> None:
        """保存当前内容宽度和位置到 config。"""
        self._config.width = self.width() - self.BORDER_WIDTH * 2
        self._config.x = self.x()
        self._config.y = self.y()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_geometry()
        self.closed.emit()
        super().closeEvent(event)
