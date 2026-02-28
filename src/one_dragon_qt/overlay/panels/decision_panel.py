from __future__ import annotations

import html
import time

from one_dragon.base.operation.overlay_debug_bus import DecisionTraceItem
from one_dragon_qt.widgets.overlay_text_widget import OverlayTextWidget
from one_dragon_qt.widgets.resizable_panel import ResizablePanel


class DecisionPanel(ResizablePanel):
    """Overlay decision trace panel."""

    def __init__(self, parent=None):
        super().__init__(title="Decision Trace", min_width=220, min_height=100, parent=parent)
        self.set_title_visible(False)
        self._text_widget = OverlayTextWidget(self)
        self.body_layout.addWidget(self._text_widget, 1)

    def set_appearance(self, font_size: int, panel_opacity: int) -> None:
        self.set_panel_opacity(panel_opacity)
        self._text_widget.set_appearance(font_size)

    def update_items(self, items: list[DecisionTraceItem]) -> None:
        rows: list[str] = []
        for item in sorted(items, key=lambda x: x.created)[-24:]:
            t = time.strftime("%H:%M:%S", time.localtime(item.created))
            source = html.escape(item.source)
            trigger = html.escape(item.trigger)
            expr = html.escape(item.expression)
            action = html.escape(item.operation)
            status = html.escape(item.status)
            rows.append(
                f"<span style='color:#9d9d9d'>[{t}]</span> "
                f"<span style='color:#67d6ff'>[{source}]</span> "
                f"<span style='color:#ffc66d'>{trigger}</span> "
                f"<span style='color:#a7a7a7'>=></span> "
                f"<span style='color:#d8e27f'>{expr}</span> "
                f"<span style='color:#a7a7a7'>/</span> "
                f"<span style='color:#f0f0f0'>{action}</span> "
                f"<span style='color:#8be28b'>[{status}]</span>"
            )
        self._text_widget.setHtml("<br>".join(rows))
