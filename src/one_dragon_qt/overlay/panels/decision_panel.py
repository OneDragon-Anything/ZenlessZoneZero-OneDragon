from __future__ import annotations

import html
import time

from one_dragon.base.operation.overlay_debug_bus import DecisionTraceItem
from one_dragon_qt.overlay.panels.resizable_panel import ResizablePanel
from one_dragon_qt.widgets.overlay_text_widget import OverlayTextWidget


class DecisionPanel(ResizablePanel):
    """Overlay decision trace panel."""

    def __init__(self, parent=None):
        super().__init__(
            title="Decision Trace", panel_name="decision_panel",
            min_width=220, min_height=100, parent=parent,
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

    def update_items(self, items: list[DecisionTraceItem]) -> None:
        if self._edit_mode:
            return
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
                f"<span style='color:{self._text_color}'>{action}</span> "
                f"<span style='color:#8be28b'>[{status}]</span>"
            )
        self._text_widget.setHtml("<br>".join(rows))
