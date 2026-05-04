from __future__ import annotations

import html
import time

from one_dragon.base.operation.overlay_debug_bus import TimelineItem
from one_dragon_qt.overlay.panels.resizable_panel import ResizablePanel
from one_dragon_qt.widgets.overlay_text_widget import OverlayTextWidget

_LEVEL_COLOR = {
    "DEBUG": "#8cb4ff",
    "INFO": "#67d6ff",
    "WARNING": "#ffd166",
    "ERROR": "#ff8c8c",
}


class TimelinePanel(ResizablePanel):
    """Overlay event timeline panel."""

    def __init__(self, parent=None):
        super().__init__(
            title="Timeline", panel_name="timeline_panel",
            min_width=220, min_height=110, parent=parent,
        )
        self.set_title_visible(False)
        self._text_color = "#f2f2f2"

        self._text_widget = OverlayTextWidget(self)
        self._edit_text_widget = self._text_widget
        self.body_layout.addWidget(self._text_widget, 1)
        self._text_widget.set_text_color(self._text_color)
        self._build_edit_toolbar()

    def set_text_color(self, color: str) -> None:
        self._text_color = str(color or "").strip() or "#f2f2f2"
        self._text_widget.set_text_color(self._text_color)

    def update_items(self, items: list[TimelineItem]) -> None:
        if self._edit_mode:
            return
        rows: list[str] = []
        for item in sorted(items, key=lambda x: x.created)[-28:]:
            t = time.strftime("%H:%M:%S", time.localtime(item.created))
            level = (item.level or "INFO").upper()
            level_color = _LEVEL_COLOR.get(level, "#d0d0d0")
            rows.append(
                f"<span style='color:#9d9d9d'>[{t}]</span> "
                f"<span style='color:{level_color}'>[{html.escape(level)}]</span> "
                f"<span style='color:#8ce6b0'>[{html.escape(item.category or '')}]</span> "
                f"<span style='color:{self._text_color}'>{html.escape(item.title or '')}</span> "
                f"<span style='color:{self._text_color}'>{html.escape(item.detail or '')}</span>"
            )
        self._text_widget.setHtml("<br>".join(rows))
