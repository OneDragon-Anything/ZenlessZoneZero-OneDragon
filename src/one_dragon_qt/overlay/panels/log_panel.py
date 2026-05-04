from __future__ import annotations

import html
import time
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer

from one_dragon_qt.overlay.overlay_events import OverlayLogEvent
from one_dragon_qt.overlay.panels.resizable_panel import ResizablePanel
from one_dragon_qt.widgets.overlay_text_widget import OverlayTextWidget


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

    def __init__(self, parent=None):
        super().__init__(
            title="Overlay Log", panel_name="log_panel",
            min_width=320, min_height=130, parent=parent,
        )
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.set_title_visible(False)
        self.set_drag_anywhere(False)

        self._max_lines = 120
        self._fade_seconds = 12
        self._lines: deque[_LogLine] = deque()
        self._text_color = "#efefef"

        self._text_widget = OverlayTextWidget(self)
        self._edit_text_widget = self._text_widget
        self.body_layout.addWidget(self._text_widget, 1)
        self._text_widget.set_text_color(self._text_color)

        self._build_edit_toolbar()

        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.timeout.connect(self._drop_expired)
        self._cleanup_timer.start(1000)

    def set_appearance(self, font_size: int, panel_opacity: int) -> None:
        super().set_appearance(font_size, panel_opacity)
        self.setWindowOpacity(self._panel_opacity / 100.0)
        self._render()

    def set_text_color(self, color: str) -> None:
        self._text_color = str(color or "").strip() or "#efefef"
        self._text_widget.set_text_color(self._text_color)
        self._render()

    def set_limits(self, max_lines: int, fade_seconds: int) -> None:
        self._max_lines = max(20, int(max_lines))
        self._fade_seconds = max(3, int(fade_seconds))
        self._drop_expired()

    def append_log(self, event: OverlayLogEvent) -> None:
        if self._edit_mode:
            return
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
        self._render()

    def clear(self) -> None:
        self._lines.clear()
        self._text_widget.clear()

    def _drop_expired(self) -> None:
        if self._edit_mode:
            return
        now = time.time()
        changed = False
        while self._lines and now - self._lines[0].created > self._fade_seconds:
            self._lines.popleft()
            changed = True
        if changed:
            self._render()

    def _render(self) -> None:
        if self._edit_mode:
            return
        if not self._lines:
            self._text_widget.setHtml("")
            return

        rows: list[str] = []
        for line in self._lines:
            level_color = _LEVEL_COLOR.get(line.level_name, "#d0d0d0")
            time_text = time.strftime("%H:%M:%S", time.localtime(line.created))
            message = html.escape(line.message)
            source = html.escape(line.source)
            row = (
                f"<span style='color:#a0a0a0'>[{time_text}]</span> "
                f"<span style='color:{level_color};font-weight:600'>[{line.level_name}]</span> "
                f"<span style='color:#c9c9c9'>[{source}]</span> "
                f"<span style='color:{self._text_color}'>{message}</span>"
            )
            rows.append(row)

        self._text_widget.setHtml("<br>".join(rows))
