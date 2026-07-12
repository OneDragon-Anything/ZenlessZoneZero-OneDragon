from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from one_dragon.base.debug.debug_trace_bus import (
    DebugTraceBus,
    DebugTraceSnapshot,
    PerfTraceItem,
    VisionTraceItem,
)
from one_dragon.base.debug.debug_trace_bus import (
    DecisionTraceItem as NewDecisionTraceItem,
)
from one_dragon.base.debug.debug_trace_bus import (
    TimelineTraceItem as NewTimelineTraceItem,
)


def _normalize_created(created: float | None) -> float:
    if created is None or created <= 0:
        return time.time()
    return float(created)


@dataclass(slots=True)
class VisionDrawItem:
    source: str
    label: str
    x1: int
    y1: int
    x2: int
    y2: int
    score: float | None = None
    color: str | None = None
    created: float = 0.0
    ttl_seconds: float = 1.8
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DecisionTraceItem:
    source: str
    trigger: str
    expression: str
    operation: str
    status: str
    created: float = 0.0
    ttl_seconds: float = 30.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TimelineItem:
    category: str
    title: str
    detail: str
    created: float = 0.0
    level: str = "INFO"
    ttl_seconds: float = 60.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PerfMetricSample:
    metric: str
    value: float
    unit: str
    created: float = 0.0
    ttl_seconds: float = 30.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OverlayDebugSnapshot:
    created: float
    vision_items: list[VisionDrawItem]
    decision_items: list[DecisionTraceItem]
    timeline_items: list[TimelineItem]
    performance_items: list[PerfMetricSample]


class OverlayDebugBus(DebugTraceBus):
    """向后兼容的 overlay 调试总线。

    继承自 DebugTraceBus，保留旧 API 兼容（VisionDrawItem 等旧数据类）。
    内部委托给父类队列存储新格式数据，snapshot() 转换回旧格式。
    逐步迁移调用方后删除此类。
    """

    def __init__(
        self,
        max_vision_items: int = 800,
        max_decision_items: int = 800,
        max_timeline_items: int = 1200,
        max_perf_items: int = 2000,
    ):
        DebugTraceBus.__init__(
            self,
            max_vision=max_vision_items,
            max_decision=max_decision_items,
            max_timeline=max_timeline_items,
            max_perf=max_perf_items,
        )
        self.enabled: bool = True
        """是否启用调试总线，由消费端（如 overlay 面板）控制"""

    # --- 兼容旧 API（接受旧数据类，转换为新格式存储） ---

    def add_vision(self, item: VisionDrawItem) -> None:
        """接受旧格式 VisionDrawItem，转换为 VisionTraceItem 存储。

        直接存到父类队列，不经父类 add_vision，避免重复应用 crop_offset
        （旧调用方在外层已手动加过偏移）。
        """
        item.created = _normalize_created(item.created)
        meta: dict | None = dict(item.meta) if item.meta else None
        if item.color:
            meta = meta or {}
            meta["_color"] = item.color
        if item.ttl_seconds:
            meta = meta or {}
            meta["_ttl_seconds"] = item.ttl_seconds
        new_item = VisionTraceItem(
            source=item.source,
            label=item.label,
            x1=item.x1,
            y1=item.y1,
            x2=item.x2,
            y2=item.y2,
            score=item.score or 0.0,
            meta=meta,
            created=item.created,
        )
        with self._lock:
            self._vision.append(new_item)

    def add_decision(self, item: DecisionTraceItem) -> None:
        """接受旧格式 DecisionTraceItem，转换为新格式存储。"""
        item.created = _normalize_created(item.created)
        meta: dict | None = dict(item.meta) if item.meta else None
        if item.ttl_seconds:
            meta = meta or {}
            meta["_ttl_seconds"] = item.ttl_seconds
        new_item = NewDecisionTraceItem(
            source=item.source,
            trigger=item.trigger,
            expression=item.expression,
            operation=item.operation,
            status=item.status,
            meta=meta,
            created=item.created,
        )
        with self._lock:
            self._decision.append(new_item)

    def add_timeline(self, item: TimelineItem) -> None:
        """接受旧格式 TimelineItem，转换为 TimelineTraceItem 存储。"""
        item.created = _normalize_created(item.created)
        meta: dict | None = dict(item.meta) if item.meta else None
        if item.ttl_seconds:
            meta = meta or {}
            meta["_ttl_seconds"] = item.ttl_seconds
        new_item = NewTimelineTraceItem(
            category=item.category,
            title=item.title,
            detail=item.detail,
            level=item.level,
            meta=meta,
            created=item.created,
        )
        with self._lock:
            self._timeline.append(new_item)

    def add_performance(self, item: PerfMetricSample) -> None:
        """接受旧格式 PerfMetricSample，转换为 PerfTraceItem 存储。"""
        item.created = _normalize_created(item.created)
        meta: dict | None = dict(item.meta) if item.meta else None
        if item.ttl_seconds:
            meta = meta or {}
            meta["_ttl_seconds"] = item.ttl_seconds
        new_item = PerfTraceItem(
            metric=item.metric,
            value=item.value,
            unit=item.unit,
            meta=meta,
            created=item.created,
        )
        with self._lock:
            self._perf.append(new_item)

    # --- 快照（返回旧格式，兼容现有 overlay 面板） ---

    def snapshot(self) -> OverlayDebugSnapshot:
        """返回旧格式 OverlayDebugSnapshot，兼容现有 overlay 面板。"""
        snap: DebugTraceSnapshot = DebugTraceBus.snapshot(self)
        return OverlayDebugSnapshot(
            created=snap.created,
            vision_items=[self._to_old_vision(v) for v in snap.vision_items],
            decision_items=[self._to_old_decision(d) for d in snap.decision_items],
            timeline_items=[self._to_old_timeline(t) for t in snap.timeline_items],
            performance_items=[self._to_old_perf(p) for p in snap.perf_items],
        )

    @staticmethod
    def _to_old_vision(item: VisionTraceItem) -> VisionDrawItem:
        meta = item.meta or {}
        return VisionDrawItem(
            source=item.source,
            label=item.label,
            x1=item.x1,
            y1=item.y1,
            x2=item.x2,
            y2=item.y2,
            score=item.score,
            color=meta.get("_color"),
            created=item.created,
            ttl_seconds=meta.get("_ttl_seconds", 1.8),
            meta={k: v for k, v in meta.items() if not k.startswith("_")},
        )

    @staticmethod
    def _to_old_decision(item: NewDecisionTraceItem) -> DecisionTraceItem:
        meta = item.meta or {}
        return DecisionTraceItem(
            source=item.source,
            trigger=item.trigger,
            expression=item.expression,
            operation=item.operation,
            status=item.status,
            created=item.created,
            ttl_seconds=meta.get("_ttl_seconds", 30.0),
            meta={k: v for k, v in meta.items() if not k.startswith("_")},
        )

    @staticmethod
    def _to_old_timeline(item: NewTimelineTraceItem) -> TimelineItem:
        meta = item.meta or {}
        return TimelineItem(
            category=item.category,
            title=item.title,
            detail=item.detail,
            created=item.created,
            level=item.level,
            ttl_seconds=meta.get("_ttl_seconds", 60.0),
            meta={k: v for k, v in meta.items() if not k.startswith("_")},
        )

    @staticmethod
    def _to_old_perf(item: PerfTraceItem) -> PerfMetricSample:
        meta = item.meta or {}
        return PerfMetricSample(
            metric=item.metric,
            value=item.value,
            unit=item.unit,
            created=item.created,
            ttl_seconds=meta.get("_ttl_seconds", 30.0),
            meta={k: v for k, v in meta.items() if not k.startswith("_")},
        )

    # --- 以下继承自 DebugTraceBus，无需覆盖 ---
    # set_crop_offset / reset_crop_offset / crop_offset
    # clear
