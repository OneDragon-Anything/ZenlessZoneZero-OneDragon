from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


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


class OverlayDebugBus:
    """
    Thread-safe runtime debug bus used by overlay modules.

    This bus has no Qt dependency and can be safely used in worker threads.
    """

    def __init__(
        self,
        max_vision_items: int = 800,
        max_decision_items: int = 800,
        max_timeline_items: int = 1200,
        max_perf_items: int = 2000,
    ):
        self._lock = threading.RLock()
        self._vision_items: deque[VisionDrawItem] = deque(maxlen=max_vision_items)
        self._decision_items: deque[DecisionTraceItem] = deque(maxlen=max_decision_items)
        self._timeline_items: deque[TimelineItem] = deque(maxlen=max_timeline_items)
        self._performance_items: deque[PerfMetricSample] = deque(maxlen=max_perf_items)

    def add_vision(self, item: VisionDrawItem) -> None:
        item.created = _normalize_created(item.created)
        with self._lock:
            self._vision_items.append(item)

    def add_decision(self, item: DecisionTraceItem) -> None:
        item.created = _normalize_created(item.created)
        with self._lock:
            self._decision_items.append(item)

    def add_timeline(self, item: TimelineItem) -> None:
        item.created = _normalize_created(item.created)
        with self._lock:
            self._timeline_items.append(item)

    def add_performance(self, item: PerfMetricSample) -> None:
        item.created = _normalize_created(item.created)
        with self._lock:
            self._performance_items.append(item)

    def clear(self) -> None:
        with self._lock:
            self._vision_items.clear()
            self._decision_items.clear()
            self._timeline_items.clear()
            self._performance_items.clear()

    def snapshot(self) -> OverlayDebugSnapshot:
        now = time.time()
        with self._lock:
            self._drop_expired(now)
            return OverlayDebugSnapshot(
                created=now,
                vision_items=list(self._vision_items),
                decision_items=list(self._decision_items),
                timeline_items=list(self._timeline_items),
                performance_items=list(self._performance_items),
            )

    def _drop_expired(self, now: float) -> None:
        self._drop_expired_from_deque(self._vision_items, now)
        self._drop_expired_from_deque(self._decision_items, now)
        self._drop_expired_from_deque(self._timeline_items, now)
        self._drop_expired_from_deque(self._performance_items, now)

    @staticmethod
    def _drop_expired_from_deque(items: deque, now: float) -> None:
        while items:
            head = items[0]
            ttl = max(0.1, float(getattr(head, "ttl_seconds", 0.0) or 0.0))
            created = float(getattr(head, "created", 0.0) or 0.0)
            if created <= 0:
                items.popleft()
                continue
            if now - created <= ttl:
                break
            items.popleft()
