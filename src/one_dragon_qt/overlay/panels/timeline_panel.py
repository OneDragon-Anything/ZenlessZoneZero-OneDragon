from __future__ import annotations

import html
import time

from one_dragon.base.operation.overlay_debug_bus import TimelineItem
from one_dragon_qt.widgets.overlay_text_widget import OverlayTextWidget
from one_dragon_qt.widgets.resizable_panel import ResizablePanel


_LEVEL_COLOR = {
    "DEBUG": "#8cb4ff",
    "INFO": "#67d6ff",
    "WARNING": "#ffd166",
    "ERROR": "#ff8c8c",
}


class TimelinePanel(ResizablePanel):
    """Overlay event timeline panel."""

    def __init__(self, parent=None):
        super().__init__(title="Timeline", min_width=220, min_height=110, parent=parent)
        self.set_title_visible(False)
        self._text_widget = OverlayTextWidget(self)
        self.body_layout.addWidget(self._text_widget, 1)

    def set_appearance(self, font_size: int, text_opacity: int, panel_opacity: int) -> None:
        self.set_panel_opacity(panel_opacity)
        self._text_widget.set_appearance(font_size, text_opacity)

    def update_items(self, items: list[TimelineItem]) -> None:
        rows: list[str] = []
        for item in sorted(items, key=lambda x: x.created)[-28:]:
            t = time.strftime("%H:%M:%S", time.localtime(item.created))
            level = (item.level or "INFO").upper()
            level_color = _LEVEL_COLOR.get(level, "#d0d0d0")
            rows.append(
                f"<span style='color:#9d9d9d'>[{t}]</span> "
                f"<span style='color:{level_color}'>[{html.escape(level)}]</span> "
                f"<span style='color:#8ce6b0'>[{html.escape(item.category or '')}]</span> "
                f"<span style='color:#f2f2f2'>{html.escape(item.title or '')}</span> "
                f"<span style='color:#a6a6a6'>{html.escape(item.detail or '')}</span>"
            )
        self._text_widget.setHtml("<br>".join(rows))
