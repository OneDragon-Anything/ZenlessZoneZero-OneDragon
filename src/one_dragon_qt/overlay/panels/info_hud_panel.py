from __future__ import annotations

import html
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from one_dragon.base.operation.overlay_debug_bus import (
    DecisionTraceItem,
    PerfMetricSample,
    TimelineItem,
)


_LEVEL_COLOR = {
    "DEBUG": "#8cb4ff",
    "INFO": "#67d6ff",
    "WARNING": "#ffd166",
    "ERROR": "#ff8c8c",
}

_CORE_METRIC_ORDER = [
    "ocr_ms",
    "yolo_ms",
    "cv_pipeline_ms",
    "operation_round_ms",
    "overlay_refresh_ms",
]


class InfoHudPanel(QWidget):
    """Afterburner-style flat-text OSD panel.

    Displays state, decision, timeline and performance data as plain
    semi-transparent text rows — no border, no background box.
    The panel is NOT interactive (always click-through).
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._font_size = 12
        self._enabled_metric_map: dict[str, bool] = {}

        self._state_items: list[tuple[str, str]] = []
        self._decision_items: list[DecisionTraceItem] = []
        self._timeline_items: list[TimelineItem] = []
        self._performance_items: list[PerfMetricSample] = []

        self._label = QLabel(self)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(0)
        layout.addWidget(self._label, 1)

        self._refresh_style()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_appearance(self, font_size: int, _panel_opacity: int = 0) -> None:
        self._font_size = max(10, min(28, int(font_size)))
        self._refresh_style()
        self._render()

    def set_enabled_metric_map(self, metric_map: dict[str, bool] | None) -> None:
        self._enabled_metric_map = dict(metric_map or {})
        self._render()

    def update_state(self, items: list[tuple[str, str]]) -> None:
        self._state_items = items
        self._render()

    def update_decisions(self, items: list[DecisionTraceItem]) -> None:
        self._decision_items = items
        self._render()

    def update_timeline(self, items: list[TimelineItem]) -> None:
        self._timeline_items = items
        self._render()

    def update_performance(self, items: list[PerfMetricSample]) -> None:
        self._performance_items = items
        self._render()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refresh_style(self) -> None:
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: transparent;
                border: none;
                color: #eaeaea;
                font-family: Consolas, 'Courier New', monospace;
                font-size: {self._font_size}px;
            }}
            """
        )
        # Text shadow via QLabel is not well supported, so we rely on the
        # semi-transparent overlay window background to provide contrast.
        _ = shadow_alpha  # suppress unused

    def _render(self) -> None:
        rows: list[str] = []
        rows.extend(self._render_state())
        rows.extend(self._render_performance())
        rows.extend(self._render_decisions())
        rows.extend(self._render_timeline())
        self._label.setText("<br>".join(rows) if rows else "")

    def _render_state(self) -> list[str]:
        if not self._state_items:
            return []
        rows: list[str] = []
        for key, value in self._state_items:
            sk = html.escape(key)
            sv = html.escape(value)
            rows.append(
                f"<span style='color:#9ecfff'>{sk}</span>"
                f"<span style='color:#808080'>: </span>"
                f"<span style='color:#f0f0f0'>{sv}</span>"
            )
        return rows

    def _render_performance(self) -> list[str]:
        if not self._performance_items:
            return []
        latest_by_metric: dict[str, PerfMetricSample] = {}
        for item in sorted(self._performance_items, key=lambda x: x.created):
            latest_by_metric[item.metric] = item

        core = [k for k in _CORE_METRIC_ORDER if k in latest_by_metric]
        rest = sorted(k for k in latest_by_metric if k not in _CORE_METRIC_ORDER)
        ordered = core + rest

        now = time.time()
        rows: list[str] = []
        for key in ordered:
            sample = latest_by_metric[key]
            if self._enabled_metric_map and not self._enabled_metric_map.get(key, False):
                continue
            age_ms = int((now - sample.created) * 1000)
            rows.append(
                f"<span style='color:#9cc4ff'>{html.escape(key)}</span>"
                f"<span style='color:#808080'>: </span>"
                f"<span style='color:#f5f5f5'>{sample.value:.1f}{html.escape(sample.unit)}</span> "
                f"<span style='color:#606060'>({age_ms}ms)</span>"
            )
        return rows

    def _render_decisions(self) -> list[str]:
        if not self._decision_items:
            return []
        rows: list[str] = []
        for item in sorted(self._decision_items, key=lambda x: x.created)[-6:]:
            t = time.strftime("%H:%M:%S", time.localtime(item.created))
            rows.append(
                f"<span style='color:#707070'>[{t}]</span> "
                f"<span style='color:#ffc66d'>{html.escape(item.trigger)}</span>"
                f"<span style='color:#808080'>=></span>"
                f"<span style='color:#d8e27f'>{html.escape(item.expression)}</span> "
                f"<span style='color:#8be28b'>[{html.escape(item.status)}]</span>"
            )
        return rows

    def _render_timeline(self) -> list[str]:
        if not self._timeline_items:
            return []
        rows: list[str] = []
        for item in sorted(self._timeline_items, key=lambda x: x.created)[-6:]:
            t = time.strftime("%H:%M:%S", time.localtime(item.created))
            level = (item.level or "INFO").upper()
            lc = _LEVEL_COLOR.get(level, "#d0d0d0")
            rows.append(
                f"<span style='color:#707070'>[{t}]</span> "
                f"<span style='color:{lc}'>[{html.escape(level)}]</span> "
                f"<span style='color:#8ce6b0'>[{html.escape(item.category)}]</span> "
                f"<span style='color:#e0e0e0'>{html.escape(item.title)}</span>"
            )
        return rows
