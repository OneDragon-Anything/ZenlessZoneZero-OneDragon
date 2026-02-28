from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ResizablePanel(QFrame):
    """Draggable and resizable overlay panel."""

    geometry_changed = Signal(dict)

    _EDGE_NONE = 0
    _EDGE_LEFT = 1
    _EDGE_RIGHT = 2
    _EDGE_TOP = 4
    _EDGE_BOTTOM = 8

    def __init__(
        self,
        title: str,
        min_width: int = 260,
        min_height: int = 140,
        parent=None,
    ):
        super().__init__(parent)
        self._title = title
        self._min_width = max(160, min_width)
        self._min_height = max(100, min_height)
        self._edge_margin = 6
        self._header_height = 28

        self._dragging = False
        self._resizing = False
        self._active_edge = self._EDGE_NONE
        self._press_global = QPoint()
        self._press_geometry = QRect()

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setMouseTracking(True)
        self.setMinimumSize(self._min_width, self._min_height)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            """
            ResizablePanel {
                background-color: rgba(15, 15, 18, 175);
                border: 1px solid rgba(255, 255, 255, 52);
                border-radius: 8px;
            }
            QLabel#overlayPanelTitle {
                color: #f0f0f0;
                font-size: 13px;
                font-weight: 600;
                padding-left: 6px;
            }
            """
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 8)
        self._layout.setSpacing(6)

        self._title_label = QLabel(self._title, self)
        self._title_label.setObjectName("overlayPanelTitle")
        self._title_label.setFixedHeight(self._header_height)
        self._layout.addWidget(self._title_label)

    @property
    def body_layout(self) -> QVBoxLayout:
        return self._layout

    def _hit_test_edge(self, pos: QPoint) -> int:
        edge = self._EDGE_NONE
        if pos.x() <= self._edge_margin:
            edge |= self._EDGE_LEFT
        elif pos.x() >= self.width() - self._edge_margin:
            edge |= self._EDGE_RIGHT

        if pos.y() <= self._edge_margin:
            edge |= self._EDGE_TOP
        elif pos.y() >= self.height() - self._edge_margin:
            edge |= self._EDGE_BOTTOM

        return edge

    def _is_in_header(self, pos: QPoint) -> bool:
        return 0 <= pos.y() <= self._header_height + 4

    def _update_cursor(self, edge: int, pos: QPoint) -> None:
        if edge in (self._EDGE_LEFT, self._EDGE_RIGHT):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in (self._EDGE_TOP, self._EDGE_BOTTOM):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif edge in (self._EDGE_LEFT | self._EDGE_TOP, self._EDGE_RIGHT | self._EDGE_BOTTOM):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in (self._EDGE_RIGHT | self._EDGE_TOP, self._EDGE_LEFT | self._EDGE_BOTTOM):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif self._is_in_header(pos):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        self._press_global = event.globalPosition().toPoint()
        self._press_geometry = self.geometry()
        self._active_edge = self._hit_test_edge(event.position().toPoint())

        if self._active_edge != self._EDGE_NONE:
            self._resizing = True
        elif self._is_in_header(event.position().toPoint()):
            self._dragging = True

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if not self._dragging and not self._resizing:
            self._update_cursor(self._hit_test_edge(pos), pos)
            super().mouseMoveEvent(event)
            return

        delta = event.globalPosition().toPoint() - self._press_global
        geom = QRect(self._press_geometry)

        if self._dragging:
            geom.moveTopLeft(self._press_geometry.topLeft() + delta)
        elif self._resizing:
            if self._active_edge & self._EDGE_LEFT:
                geom.setLeft(self._press_geometry.left() + delta.x())
            if self._active_edge & self._EDGE_RIGHT:
                geom.setRight(self._press_geometry.right() + delta.x())
            if self._active_edge & self._EDGE_TOP:
                geom.setTop(self._press_geometry.top() + delta.y())
            if self._active_edge & self._EDGE_BOTTOM:
                geom.setBottom(self._press_geometry.bottom() + delta.y())

        geom = self._normalize_geometry(geom)
        self.setGeometry(geom)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        changed = self._dragging or self._resizing
        self._dragging = False
        self._resizing = False
        self._active_edge = self._EDGE_NONE
        self.setCursor(Qt.CursorShape.ArrowCursor)

        if changed:
            g = self.geometry()
            self.geometry_changed.emit(
                {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()}
            )

        super().mouseReleaseEvent(event)

    def _normalize_geometry(self, geom: QRect) -> QRect:
        parent = self.parentWidget()
        if geom.width() < self._min_width:
            if self._active_edge & self._EDGE_LEFT:
                geom.setLeft(geom.right() - self._min_width + 1)
            else:
                geom.setWidth(self._min_width)
        if geom.height() < self._min_height:
            if self._active_edge & self._EDGE_TOP:
                geom.setTop(geom.bottom() - self._min_height + 1)
            else:
                geom.setHeight(self._min_height)

        if parent is None:
            return geom

        max_x = max(0, parent.width() - geom.width())
        max_y = max(0, parent.height() - geom.height())

        if geom.x() < 0:
            geom.moveLeft(0)
        elif geom.x() > max_x:
            geom.moveLeft(max_x)

        if geom.y() < 0:
            geom.moveTop(0)
        elif geom.y() > max_y:
            geom.moveTop(max_y)

        if geom.right() > parent.width():
            geom.moveRight(parent.width())
        if geom.bottom() > parent.height():
            geom.moveBottom(parent.height())

        return geom
