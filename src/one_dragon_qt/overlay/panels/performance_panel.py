from __future__ import annotations

import html
import time

from one_dragon.base.operation.overlay_debug_bus import PerfMetricSample
from one_dragon_qt.widgets.overlay_text_widget import OverlayTextWidget
from one_dragon_qt.widgets.resizable_panel import ResizablePanel


_CORE_METRIC_ORDER = [
    "ocr_ms",
    "yolo_ms",
    "cv_pipeline_ms",
    "operation_round_ms",
    "overlay_refresh_ms",
]


class PerformancePanel(ResizablePanel):
    """Overlay performance panel."""

    def __init__(self, parent=None):
        super().__init__(title="Performance", min_width=220, min_height=90, parent=parent)
        self.set_title_visible(False)
        self._text_widget = OverlayTextWidget(self)
        self.body_layout.addWidget(self._text_widget, 1)
        self._enabled_metric_map: dict[str, bool] = {}

    def set_appearance(self, font_size: int, panel_opacity: int) -> None:
        self.set_panel_opacity(panel_opacity)
        self._text_widget.set_appearance(font_size)

    def set_enabled_metric_map(self, metric_map: dict[str, bool] | None) -> None:
        self._enabled_metric_map = dict(metric_map or {})

    def update_items(self, items: list[PerfMetricSample]) -> None:
        latest_by_metric: dict[str, PerfMetricSample] = {}
        for item in sorted(items, key=lambda x: x.created):
            latest_by_metric[item.metric] = item

        metric_keys = self._sorted_metric_keys(latest_by_metric.keys())

        now = time.time()
        rows: list[str] = []
        for key in metric_keys:
            sample = latest_by_metric.get(key)
            if sample is None:
                continue
            if self._enabled_metric_map and not self._enabled_metric_map.get(key, False):
                continue
            age_ms = int((now - sample.created) * 1000)
            rows.append(
                f"<span style='color:#9cc4ff'>{html.escape(key)}</span>"
                f"<span style='color:#a6a6a6'>: </span>"
                f"<span style='color:#f5f5f5'>{sample.value:.2f} {html.escape(sample.unit)}</span> "
                f"<span style='color:#7f7f7f'>({age_ms}ms ago)</span>"
            )
        self._text_widget.setHtml("<br>".join(rows))

    @staticmethod
    def _sorted_metric_keys(metric_keys) -> list[str]:
        core = [key for key in _CORE_METRIC_ORDER if key in metric_keys]
        rest = sorted([key for key in metric_keys if key not in _CORE_METRIC_ORDER])
        return core + rest
