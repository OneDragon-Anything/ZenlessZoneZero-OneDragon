from __future__ import annotations

import html

from one_dragon_qt.widgets.overlay_text_widget import OverlayTextWidget
from one_dragon_qt.widgets.resizable_panel import ResizablePanel


class StatePanel(ResizablePanel):
    """Overlay run-state panel."""

    def __init__(self, parent=None):
        super().__init__(title="Overlay State", min_width=280, min_height=180, parent=parent)
        self._text_widget = OverlayTextWidget(self)
        self.body_layout.addWidget(self._text_widget, 1)

    def update_snapshot(self, items: list[tuple[str, str]]) -> None:
        rows: list[str] = []
        for key, value in items:
            safe_key = html.escape(key)
            safe_value = html.escape(value)
            rows.append(
                f"<span style='color:#9ecfff;font-weight:600'>{safe_key}</span>"
                f"<span style='color:#9f9f9f'>: </span>"
                f"<span style='color:#f2f2f2'>{safe_value}</span>"
            )
        self._text_widget.setHtml("<br>".join(rows))

