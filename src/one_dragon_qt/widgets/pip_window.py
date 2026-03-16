from __future__ import annotations

from collections.abc import Callable

from cv2.typing import MatLike
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QWidget

from one_dragon_qt.services.pip.pip_capture_worker import PipCaptureWorker


class PipWindow(QWidget):
    """画中画窗口 - 始终置顶的无边框半透明截图预览窗口

    独立线程截图，左键单击发出 clicked 信号，左键拖拽移动，
    边缘拖拽缩放(保持16:9)，右键关闭。
    """

    clicked = Signal()
    closed = Signal()

    ASPECT_W: int = 16
    ASPECT_H: int = 9
    BORDER_WIDTH: int = 2
    EDGE_ZONE: int = 8
    DRAG_THRESHOLD: int = 5
    MIN_WIDTH: int = 320
    MAX_WIDTH: int = 1920
    DEFAULT_WIDTH: int = 480
    DEFAULT_FPS: int = 30

    def __init__(
        self,
        capture_fn: Callable[[], MatLike | None],
        target_fps: int = DEFAULT_FPS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._frame: QPixmap | None = None

        # 拖拽状态
        self._dragging: bool = False
        self._drag_start_pos: QPoint | None = None
        self._press_global_pos: QPoint | None = None  # 用于区分点击和拖拽

        # 缩放状态
        self._resizing: bool = False
        self._resize_edge: str = ''
        self._resize_start_rect: QRect | None = None
        self._resize_start_mouse: QPoint | None = None

        # 右键关闭：press 标记，release 关闭，避免事件穿透
        self._right_pressed: bool = False

        default_h = self.DEFAULT_WIDTH * self.ASPECT_H // self.ASPECT_W
        self.resize(self.DEFAULT_WIDTH, default_h)

        # 独立截图线程
        self._worker = PipCaptureWorker(capture_fn, target_fps, self)
        self._worker.frame_ready.connect(self._on_frame_ready)
        self._worker.start()

        self.setMouseTracking(True)
        self._move_to_bottom_right()

    # ------------------------------------------------------------------
    # 截图刷新 (主线程接收)
    # ------------------------------------------------------------------

    def _on_frame_ready(self, q_image: QImage) -> None:
        self._frame = QPixmap.fromImage(q_image)
        self.update()

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        b = self.BORDER_WIDTH
        rect = self.rect()

        # 半透明边框
        border_color = QColor(0, 200, 200, 160)
        painter.setPen(QPen(border_color, b))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect.adjusted(b // 2, b // 2, -(b // 2 + 1), -(b // 2 + 1)))

        # 内容区
        content_rect = rect.adjusted(b, b, -b, -b)
        if self._frame is not None:
            painter.drawPixmap(content_rect, self._frame)
        else:
            painter.fillRect(content_rect, QColor(0, 0, 0, 200))

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
            self.setCursor(self._edge_to_cursor(edge) if edge else Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton and self._right_pressed:
            self._right_pressed = False
            self.close()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if not self._dragging and not self._resizing and self._press_global_pos is not None:
                self.clicked.emit()

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

        if ('r' not in edge and 'l' not in edge) and ('b' in edge or 't' in edge):
            new_h = r.height() + dy if 'b' in edge else r.height() - dy
            new_w = new_h * self.ASPECT_W // self.ASPECT_H

        new_w = max(self.MIN_WIDTH, min(self.MAX_WIDTH, new_w))
        new_h = new_w * self.ASPECT_H // self.ASPECT_W

        new_x = r.right() - new_w + 1 if 'l' in edge else r.x()
        new_y = r.bottom() - new_h + 1 if 't' in edge else r.y()

        self.setGeometry(new_x, new_y, new_w, new_h)

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

    def closeEvent(self, event: QCloseEvent) -> None:
        self._worker.stop()
        self.closed.emit()
        super().closeEvent(event)
