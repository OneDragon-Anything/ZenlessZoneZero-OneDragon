from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

WM_NCHITTEST = 0x0084
HTTRANSPARENT = -1


class ResizablePanel(QFrame):
    """Draggable and resizable overlay panel with built-in edit mode."""

    geometry_changed = Signal(dict)
    appearance_changed = Signal(str, int, int)
    edit_mode_changed = Signal(bool)
    free_mode_changed = Signal(str, bool)

    _EDGE_NONE = 0
    _EDGE_LEFT = 1
    _EDGE_RIGHT = 2
    _EDGE_TOP = 4
    _EDGE_BOTTOM = 8

    def __init__(
        self,
        title: str,
        panel_name: str = "",
        min_width: int = 260,
        min_height: int = 140,
        parent=None,
    ):
        super().__init__(parent)
        self._title = title
        self._panel_name = panel_name or title
        self._min_width = max(160, min_width)
        self._min_height = max(100, min_height)
        self._edge_margin = 6
        self._header_height = 28
        self._drag_handle_height = self._header_height + 4
        self._title_visible = True
        self._panel_opacity = 70
        self._font_size = 12
        self._edit_mode = False
        self._free_mode = False
        self._interaction_enabled = True
        self._drag_anywhere = False
        self._passthrough_on_body = False

        self._dragging = False
        self._resizing = False
        self._active_edge = self._EDGE_NONE
        self._press_global = QPoint()
        self._press_geometry = QRect()
        self._background_color = QColor(12, 12, 14, 180)
        self._border_color = QColor(255, 255, 255, 40)
        self._border_radius = 5
        self._border_width = 1

        # Subclasses should assign the main text widget here for edit-mode mouse passthrough.
        self._edit_text_widget: QWidget | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("overlayPanel")
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumSize(self._min_width, self._min_height)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(5, 4, 5, 5)
        self._layout.setSpacing(3)

        self._title_label = QLabel(self._title, self)
        self._title_label.setObjectName("overlayPanelTitle")
        self._title_label.setFixedHeight(self._header_height)
        self._layout.addWidget(self._title_label)
        self._refresh_style()

    @property
    def body_layout(self) -> QVBoxLayout:
        return self._layout

    def set_title_visible(self, visible: bool) -> None:
        self._title_visible = bool(visible)
        self._title_label.setVisible(self._title_visible)
        self._title_label.setFixedHeight(self._header_height if self._title_visible else 0)
        if self._title_visible:
            self._layout.setContentsMargins(5, 4, 5, 5)
            self._layout.setSpacing(3)
            self._drag_handle_height = self._header_height + 4
        else:
            self._layout.setContentsMargins(4, 4, 4, 4)
            self._layout.setSpacing(2)
            self._drag_handle_height = 12

    def set_interaction_enabled(self, enabled: bool) -> None:
        self._interaction_enabled = bool(enabled)
        if not self._interaction_enabled:
            self._dragging = False
            self._resizing = False
            self._active_edge = self._EDGE_NONE
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_drag_anywhere(self, enabled: bool) -> None:
        self._drag_anywhere = bool(enabled)

    def set_passthrough_on_body(self, enabled: bool) -> None:
        """
        When enabled on Windows, normal clicks on the panel body pass through
        to the game window. Resize edges and drag header remain interactive.
        """
        self._passthrough_on_body = bool(enabled)

    def set_panel_opacity(self, opacity_percent: int) -> None:
        self._panel_opacity = max(5, min(100, int(opacity_percent)))
        self._refresh_style()

    def set_free_mode(self, enabled: bool) -> None:
        self._free_mode = bool(enabled)
        self._refresh_style()
        self._sync_toolbar_state()

    def _refresh_style(self) -> None:
        panel_alpha = int(255 * self._panel_opacity / 100.0)
        if self._free_mode:
            background_alpha = max(132, panel_alpha)
            border_alpha = max(72, min(150, int(background_alpha * 0.52)))
            border_radius = 14
            border_width = 2
            self._background_color = QColor(80, 80, 80, background_alpha)
            self._border_color = QColor(255, 255, 255, border_alpha)
            panel_style = """
            #overlayPanel {
                background-color: transparent;
                border: none;
            }
            """
        else:
            background_alpha = panel_alpha
            border_alpha = max(18, min(90, int(panel_alpha * 0.22)))
            border_radius = 5
            border_width = 1
            self._background_color = QColor(12, 12, 14, background_alpha)
            self._border_color = QColor(255, 255, 255, border_alpha)
            panel_style = f"""
            #overlayPanel {{
                background-color: rgba(12, 12, 14, {background_alpha});
                border: {border_width}px solid rgba(255, 255, 255, {border_alpha});
                border-radius: {border_radius}px;
            }}
            """
        self._border_radius = border_radius
        self._border_width = border_width
        self.setStyleSheet(
            f"""
            {panel_style}
            QLabel#overlayPanelTitle {{
                color: #f0f0f0;
                font-size: 12px;
                font-weight: 600;
                padding-left: 4px;
            }}
            """
        )
        # WA_TranslucentBackground 窗口 setStyleSheet 不一定自动触发重绘
        self.update()

    # ------------------------------------------------------------------
    # Edit-mode support (toolbar, gray background, font / opacity)
    # ------------------------------------------------------------------

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = bool(enabled)
        self.set_interaction_enabled(self._edit_mode)
        self.set_drag_anywhere(self._edit_mode)
        if self._edit_text_widget is not None:
            self._edit_text_widget.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, self._edit_mode
            )
        if hasattr(self, "_toolbar"):
            self._toolbar.setVisible(self._edit_mode)
        if self._edit_mode:
            self._show_edit_placeholder()
        self._sync_toolbar_state()
        self.update()

    def _show_edit_placeholder(self) -> None:
        """Fill text widget with numbered placeholder lines for layout preview."""
        tw = self._edit_text_widget
        if tw is None:
            return
        if hasattr(tw, "visible_line_count"):
            n = tw.visible_line_count()
            if n <= 1:
                n = 8
        else:
            n = 8
        lines = [self._title] + [f"Line {i + 1}" for i in range(n - 1)]
        tw.setHtml("<br>".join(lines))

    def set_appearance(self, font_size: int, panel_opacity: int) -> None:
        self._font_size = max(10, min(28, int(font_size)))
        self._panel_opacity = max(5, min(100, int(panel_opacity)))
        self.set_panel_opacity(self._panel_opacity)
        if self._edit_text_widget is not None and hasattr(self._edit_text_widget, "set_appearance"):
            self._edit_text_widget.set_appearance(self._font_size)
        self._sync_toolbar_state()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._free_mode:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            border_rect = self.rect().adjusted(
                self._border_width // 2,
                self._border_width // 2,
                -(self._border_width // 2) - 1,
                -(self._border_width // 2) - 1,
            )
            path = QPainterPath()
            path.addRoundedRect(border_rect, self._border_radius, self._border_radius)
            painter.fillPath(path, self._background_color)
            if self._edit_mode:
                painter.fillPath(path, QColor(80, 80, 80, 120))
            painter.setPen(QPen(self._border_color, self._border_width))
            painter.drawPath(path)
            painter.end()
        elif self._edit_mode:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.fillRect(self.rect(), QColor(80, 80, 80, 180))
            painter.end()
        super().paintEvent(event)

    def _build_edit_toolbar(self) -> None:
        """Build the standard edit-mode toolbar. Call once at the end of subclass __init__."""
        toolbar_id = f"overlay{self._panel_name.replace('_', '')}Toolbar"
        self._toolbar = QWidget(self)
        self._toolbar.setObjectName(toolbar_id)
        self._toolbar.setFixedHeight(28)
        self._toolbar.setStyleSheet(
            f"QWidget#{toolbar_id} {{ background-color: transparent; border: none; }}"
        )
        layout = QHBoxLayout(self._toolbar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)

        self._status_label = QLabel("", self._toolbar)
        self._status_label.setStyleSheet(
            "QLabel { color: #c0c0c0; font-size: 10px; background: transparent; border: none; }"
        )
        self._status_label.setFixedHeight(20)
        layout.addWidget(self._status_label, 0)
        layout.addStretch(1)

        self._btn_font_dec = self._create_toolbar_button("A\u2212", "减小字号 (Ctrl+滚轮下)", self._on_font_dec)
        layout.addWidget(self._btn_font_dec)
        self._btn_font_inc = self._create_toolbar_button("A\u207A", "增大字号 (Ctrl+滚轮上)", self._on_font_inc)
        layout.addWidget(self._btn_font_inc)
        self._btn_panel_dec = self._create_toolbar_button("\u25A3\u2212", "降低面板不透明度", self._on_panel_dec)
        layout.addWidget(self._btn_panel_dec)
        self._btn_panel_inc = self._create_toolbar_button("\u25A3\u207A", "提高面板不透明度", self._on_panel_inc)
        layout.addWidget(self._btn_panel_inc)
        self._btn_mode_toggle = self._create_toolbar_button("", "切换锁定/自由模式", self._on_toggle_free_mode, 44)
        layout.addWidget(self._btn_mode_toggle)
        self._btn_close_edit = self._create_toolbar_button("\u2715", "关闭编辑模式", self._on_close_edit_mode)
        layout.addWidget(self._btn_close_edit)

        self.body_layout.addWidget(self._toolbar, 0)
        self._toolbar.setVisible(False)
        self._sync_toolbar_state()

    def _create_toolbar_button(self, text: str, tip: str, handler, width: int = 32) -> QToolButton:
        btn = QToolButton(self)
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(width, 22)
        btn.clicked.connect(lambda _checked=False: handler())
        btn.setStyleSheet(
            "QToolButton { background-color: rgba(190,190,190,160); color: #1e1e1e;"
            " border: none; border-radius: 4px; font-size: 12px; font-weight: 600; padding: 0px; }"
            "QToolButton:hover { background-color: rgba(210,210,210,190); }"
            "QToolButton:pressed { background-color: rgba(168,168,168,200); }"
        )
        return btn

    def _on_font_dec(self) -> None:
        if self._edit_mode:
            self._emit_appearance(max(10, self._font_size - 1), self._panel_opacity)

    def _on_font_inc(self) -> None:
        if self._edit_mode:
            self._emit_appearance(min(28, self._font_size + 1), self._panel_opacity)

    def _on_panel_dec(self) -> None:
        if self._edit_mode:
            self._emit_appearance(self._font_size, max(5, self._panel_opacity - 5))

    def _on_panel_inc(self) -> None:
        if self._edit_mode:
            self._emit_appearance(self._font_size, min(100, self._panel_opacity + 5))

    def _on_toggle_free_mode(self) -> None:
        if not self._edit_mode:
            return
        self.set_free_mode(not self._free_mode)
        self.free_mode_changed.emit(self._panel_name, self._free_mode)

    def _on_close_edit_mode(self) -> None:
        self.set_edit_mode(False)
        self.edit_mode_changed.emit(False)

    def _emit_appearance(self, font_size: int, panel_opacity: int) -> None:
        self.set_appearance(font_size, panel_opacity)
        self.appearance_changed.emit(self._panel_name, self._font_size, self._panel_opacity)

    def _sync_toolbar_state(self) -> None:
        if hasattr(self, "_status_label"):
            mode_text = "EDIT" if self._edit_mode else "PASS"
            dock_text = "FREE" if self._free_mode else "LOCK"
            self._status_label.setText(f"{mode_text} {dock_text} F{self._font_size} P{self._panel_opacity}")
        if hasattr(self, "_btn_mode_toggle"):
            if self._free_mode:
                self._btn_mode_toggle.setText("自由")
                self._btn_mode_toggle.setToolTip("切换到锁定模式")
            else:
                self._btn_mode_toggle.setText("锁定")
                self._btn_mode_toggle.setToolTip("切换到自由模式")

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._edit_mode and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._on_font_inc()
            elif delta < 0:
                self._on_font_dec()
            event.accept()
            return
        super().wheelEvent(event)

    # ------------------------------------------------------------------
    # Hit-testing / drag / resize
    # ------------------------------------------------------------------

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
        return 0 <= pos.y() <= self._drag_handle_height

    def _update_cursor(self, edge: int, pos: QPoint) -> None:
        if edge in (self._EDGE_LEFT, self._EDGE_RIGHT):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in (self._EDGE_TOP, self._EDGE_BOTTOM):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif edge in (self._EDGE_LEFT | self._EDGE_TOP, self._EDGE_RIGHT | self._EDGE_BOTTOM):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in (self._EDGE_RIGHT | self._EDGE_TOP, self._EDGE_LEFT | self._EDGE_BOTTOM):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif self._drag_anywhere or self._is_in_header(pos):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._interaction_enabled:
            super().mousePressEvent(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        self._press_global = event.globalPosition().toPoint()
        self._press_geometry = self.geometry()
        self._active_edge = self._hit_test_edge(event.position().toPoint())

        if self._active_edge != self._EDGE_NONE:
            self._resizing = True
        elif self._drag_anywhere or self._is_in_header(event.position().toPoint()):
            self._dragging = True

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._interaction_enabled:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            super().mouseMoveEvent(event)
            return
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
        if not self._interaction_enabled:
            super().mouseReleaseEvent(event)
            return
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
            # Top-level window: clamp to screen available geometry
            screen = QGuiApplication.screenAt(geom.center())
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                if geom.left() < avail.left():
                    geom.moveLeft(avail.left())
                if geom.top() < avail.top():
                    geom.moveTop(avail.top())
                if geom.right() > avail.right():
                    geom.moveLeft(max(avail.left(), avail.right() - geom.width()))
                if geom.bottom() > avail.bottom():
                    geom.moveTop(max(avail.top(), avail.bottom() - geom.height()))
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

        return geom

    def nativeEvent(self, eventType, message):
        if (
            not self._passthrough_on_body
            or not self._interaction_enabled
            or not sys.platform.startswith("win")
        ):
            return super().nativeEvent(eventType, message)

        try:
            msg = wintypes.MSG.from_address(int(message))
            if int(msg.message) != WM_NCHITTEST:
                return super().nativeEvent(eventType, message)

            lparam = int(msg.lParam)
            gx = ctypes.c_short(lparam & 0xFFFF).value
            gy = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            local = self.mapFromGlobal(QPoint(gx, gy))

            if not QRect(0, 0, self.width(), self.height()).contains(local):
                return super().nativeEvent(eventType, message)

            edge = self._hit_test_edge(local)
            if edge != self._EDGE_NONE:
                return super().nativeEvent(eventType, message)
            if self._drag_anywhere or self._is_in_header(local):
                return super().nativeEvent(eventType, message)

            # Let underlying game window receive direct clicks.
            return True, HTTRANSPARENT
        except Exception:
            return super().nativeEvent(eventType, message)
