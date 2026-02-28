from __future__ import annotations

import html
import time
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from one_dragon_qt.overlay.overlay_events import OverlayLogEvent
from one_dragon_qt.widgets.overlay_text_widget import OverlayTextWidget
from one_dragon_qt.widgets.resizable_panel import ResizablePanel


@dataclass(slots=True)
class _LogLine:
    created: float
    level_name: str
    message: str
    source: str


_LEVEL_COLOR = {
    "DEBUG": "#8cb4ff",
    "INFO": "#6ad192",
    "WARNING": "#ffcb6b",
    "ERROR": "#ff7c7c",
    "CRITICAL": "#ff5f5f",
}


class LogPanel(ResizablePanel):
    """Overlay log panel."""
    appearance_changed = Signal(int, int, int)

    def __init__(self, parent=None):
        super().__init__(title="Overlay Log", min_width=320, min_height=130, parent=parent)
        # 无边框独立窗口, 在构造时设置避免系统标题栏
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.set_title_visible(False)
        self.set_drag_anywhere(True)

        self._max_lines = 120
        self._fade_seconds = 12
        self._lines: deque[_LogLine] = deque()
        self._font_size = 12
        self._text_opacity = 100
        self._panel_opacity = 70
        self._paused = False
        self._auto_scroll = True

        self._text_widget = OverlayTextWidget(self)
        self.body_layout.addWidget(self._text_widget, 1)
        self._build_toolbar()

        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.timeout.connect(self._drop_expired)
        self._cleanup_timer.start(1000)

    def set_appearance(self, font_size: int, text_opacity: int, panel_opacity: int) -> None:
        self._font_size = max(10, min(28, int(font_size)))
        self._text_opacity = max(20, min(100, int(text_opacity)))
        self._panel_opacity = max(20, min(100, int(panel_opacity)))
        self.set_panel_opacity(self._panel_opacity)
        self._text_widget.set_appearance(self._font_size, self._text_opacity)
        self._sync_toolbar_state()

    def set_limits(self, max_lines: int, fade_seconds: int) -> None:
        self._max_lines = max(20, int(max_lines))
        self._fade_seconds = max(3, int(fade_seconds))
        self._drop_expired(force=True)

    def append_log(self, event: OverlayLogEvent) -> None:
        source = f"{event.filename}:{event.lineno}"
        self._lines.append(
            _LogLine(
                created=event.created,
                level_name=event.level_name.upper(),
                message=event.message,
                source=source,
            )
        )
        while len(self._lines) > self._max_lines:
            self._lines.popleft()
        if self._paused:
            return
        self._render()

    def clear(self) -> None:
        self._lines.clear()
        self._text_widget.clear()

    def _drop_expired(self, force: bool = False) -> None:
        if force:
            now = time.time()
        else:
            now = time.time()

        changed = False
        while self._lines and now - self._lines[0].created > self._fade_seconds:
            self._lines.popleft()
            changed = True

        if changed and not self._paused:
            self._render()

    @staticmethod
    def _apply_alpha(hex_color: str, alpha_fraction: float) -> str:
        """将 #rrggbb 颜色转为 rgba(r,g,b,a) 字符串."""
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        a = max(0.0, min(1.0, alpha_fraction))
        return f"rgba({r},{g},{b},{a:.2f})"

    def _render(self) -> None:
        if not self._lines:
            self._text_widget.setHtml("")
            return

        alpha = self._text_opacity / 100.0
        rows: list[str] = []
        for line in self._lines:
            level_color = _LEVEL_COLOR.get(line.level_name, "#d0d0d0")
            time_text = time.strftime("%H:%M:%S", time.localtime(line.created))
            message = html.escape(line.message)
            source = html.escape(line.source)
            c_time = self._apply_alpha("#a0a0a0", alpha)
            c_level = self._apply_alpha(level_color, alpha)
            c_src = self._apply_alpha("#c9c9c9", alpha)
            c_msg = self._apply_alpha("#efefef", alpha)
            row = (
                f"<span style='color:{c_time}'>[{time_text}]</span> "
                f"<span style='color:{c_level};font-weight:600'>[{line.level_name}]</span> "
                f"<span style='color:{c_src}'>[{source}]</span> "
                f"<span style='color:{c_msg}'>{message}</span>"
            )
            rows.append(row)

        self._text_widget.setHtml("<br>".join(rows))
        if self._auto_scroll:
            self._text_widget.verticalScrollBar().setValue(
                self._text_widget.verticalScrollBar().maximum()
            )

    def _build_toolbar(self) -> None:
        toolbar = QWidget(self)
        toolbar.setObjectName("overlayLogToolbar")
        toolbar.setFixedHeight(28)
        toolbar.setStyleSheet(
            """
            QWidget#overlayLogToolbar {
                background-color: rgba(120, 120, 120, 55);
                border-top: 1px solid rgba(255, 255, 255, 45);
            }
            """
        )
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(3)

        # Status indicator label
        self._status_label = QLabel("", toolbar)
        self._status_label.setStyleSheet(
            "QLabel { color: #c0c0c0; font-size: 10px; background: transparent; border: none; }"
        )
        self._status_label.setFixedHeight(20)
        layout.addWidget(self._status_label, 0)

        layout.addStretch(1)

        # Unicode icon buttons — 创建并添加到 toolbar layout
        self._btn_font_dec = self._create_button("A\u2212", "减小字号 (Ctrl+滚轮下)", self._on_font_dec)
        layout.addWidget(self._btn_font_dec)
        self._btn_font_inc = self._create_button("A\u207A", "增大字号 (Ctrl+滚轮上)", self._on_font_inc)
        layout.addWidget(self._btn_font_inc)
        self._btn_text_dec = self._create_button("\u25D1\u2212", "降低文字不透明度", self._on_text_dec)
        layout.addWidget(self._btn_text_dec)
        self._btn_text_inc = self._create_button("\u25D1\u207A", "提高文字不透明度", self._on_text_inc)
        layout.addWidget(self._btn_text_inc)
        self._btn_panel_dec = self._create_button("\u25A3\u2212", "降低面板不透明度", self._on_panel_dec)
        layout.addWidget(self._btn_panel_dec)
        self._btn_panel_inc = self._create_button("\u25A3\u207A", "提高面板不透明度", self._on_panel_inc)
        layout.addWidget(self._btn_panel_inc)
        self._btn_pause = self._create_button("\u23F8", "暂停/恢复日志刷新", self._on_pause_toggle)
        layout.addWidget(self._btn_pause)
        self._btn_autoscroll = self._create_button("\u21E9", "自动滚动开关", self._on_autoscroll_toggle)
        layout.addWidget(self._btn_autoscroll)
        self._btn_clear = self._create_button("\u2715", "清空日志", self.clear)
        layout.addWidget(self._btn_clear)

        self.body_layout.addWidget(toolbar, 0)
        self._sync_toolbar_state()

    def _create_button(self, text: str, tip: str, handler) -> QToolButton:
        btn = QToolButton(self)
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(32, 22)
        btn.clicked.connect(lambda _checked=False: handler())
        btn.setStyleSheet(
            """
            QToolButton {
                background-color: rgba(190, 190, 190, 160);
                color: #1e1e1e;
                border: 1px solid rgba(255, 255, 255, 110);
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: rgba(210, 210, 210, 190);
            }
            QToolButton:pressed {
                background-color: rgba(168, 168, 168, 200);
            }
            """
        )
        return btn

    def _on_font_dec(self) -> None:
        self._emit_appearance(max(10, self._font_size - 1), self._text_opacity, self._panel_opacity)

    def _on_font_inc(self) -> None:
        self._emit_appearance(min(28, self._font_size + 1), self._text_opacity, self._panel_opacity)

    def _on_text_dec(self) -> None:
        self._emit_appearance(self._font_size, max(20, self._text_opacity - 5), self._panel_opacity)

    def _on_text_inc(self) -> None:
        self._emit_appearance(self._font_size, min(100, self._text_opacity + 5), self._panel_opacity)

    def _on_panel_dec(self) -> None:
        self._emit_appearance(self._font_size, self._text_opacity, max(20, self._panel_opacity - 5))

    def _on_panel_inc(self) -> None:
        self._emit_appearance(self._font_size, self._text_opacity, min(100, self._panel_opacity + 5))

    def _on_pause_toggle(self) -> None:
        self._paused = not self._paused
        self._sync_toolbar_state()
        if not self._paused:
            self._render()

    def _on_autoscroll_toggle(self) -> None:
        self._auto_scroll = not self._auto_scroll
        self._sync_toolbar_state()

    def _emit_appearance(self, font_size: int, text_opacity: int, panel_opacity: int) -> None:
        self.set_appearance(font_size, text_opacity, panel_opacity)
        self.appearance_changed.emit(self._font_size, self._text_opacity, self._panel_opacity)

    def _sync_toolbar_state(self) -> None:
        if hasattr(self, "_btn_pause"):
            self._btn_pause.setText("\u25B6" if self._paused else "\u23F8")
        if hasattr(self, "_btn_autoscroll"):
            self._btn_autoscroll.setText("\u21E9" if self._auto_scroll else "\u2193")
        if hasattr(self, "_status_label"):
            pause_text = "PAUSED" if self._paused else ""
            scroll_text = "AUTO" if self._auto_scroll else "LOCK"
            parts = [f"F{self._font_size}", f"T{self._text_opacity}", f"P{self._panel_opacity}"]
            if pause_text:
                parts.append(pause_text)
            parts.append(scroll_text)
            self._status_label.setText(" ".join(parts))

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Ctrl+scroll-wheel adjusts font size."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._on_font_inc()
            elif delta < 0:
                self._on_font_dec()
            event.accept()
            return
        super().wheelEvent(event)

