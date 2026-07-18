"""通用调试 trace 总线。

框架级可选调试事件通道。核心层只产出通用 trace 数据，
不知道谁来消费、怎么展示。Overlay 只是其中一个消费者。

与旧的 OverlayDebugBus 的关键差异：
- 数据类不再包含 color、ttl_seconds（展示逻辑归消费端）
- 类名从 Overlay* 改为通用 Debug*
- 去掉 _drop_expired（消费端决定怎么处理过期）
- 去掉 offset_recent_vision（未使用）
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class VisionTraceItem:
    """视觉识别 trace 项。"""
    source: str
    label: str
    x1: int
    y1: int
    x2: int
    y2: int
    score: float = 0.0
    meta: dict | None = None
    created: float = 0.0


@dataclass(slots=True)
class DecisionTraceItem:
    """决策/流转 trace 项。"""
    source: str
    trigger: str
    expression: str
    operation: str
    status: str
    meta: dict | None = None
    created: float = 0.0


@dataclass(slots=True)
class TimelineTraceItem:
    """时间线事件 trace 项。"""
    category: str
    title: str
    detail: str = ""
    level: str = "INFO"
    meta: dict | None = None
    created: float = 0.0


@dataclass(slots=True)
class PerfTraceItem:
    """性能指标 trace 项。"""
    metric: str
    value: float
    unit: str = ""
    meta: dict | None = None
    created: float = 0.0


@dataclass(slots=True)
class DebugTraceSnapshot:
    """一次调试数据快照。"""
    vision_items: list[VisionTraceItem] = field(default_factory=list)
    decision_items: list[DecisionTraceItem] = field(default_factory=list)
    timeline_items: list[TimelineTraceItem] = field(default_factory=list)
    perf_items: list[PerfTraceItem] = field(default_factory=list)
    created: float = 0.0


def _normalize_created(created: float) -> float:
    """标准化创建时间戳。"""
    if created <= 0:
        return time.time()
    return float(created)


class DebugTraceBus:
    """通用调试 trace 总线。

    线程安全。核心层通过此总线产出 trace 数据，
    消费者通过 snapshot() 获取当前快照。
    """

    def __init__(
        self,
        max_vision: int = 800,
        max_decision: int = 800,
        max_timeline: int = 1200,
        max_perf: int = 2000,
    ) -> None:
        self._lock = threading.RLock()
        self._vision: deque[VisionTraceItem] = deque(maxlen=max_vision)
        self._decision: deque[DecisionTraceItem] = deque(maxlen=max_decision)
        self._timeline: deque[TimelineTraceItem] = deque(maxlen=max_timeline)
        self._perf: deque[PerfTraceItem] = deque(maxlen=max_perf)
        self._local = threading.local()

    # --- crop_offset（每线程） ---

    def set_crop_offset(self, x: int, y: int) -> None:
        """设置当前线程的裁剪偏移。"""
        self._local.crop_x = x
        self._local.crop_y = y

    def reset_crop_offset(self) -> None:
        """重置当前线程的裁剪偏移为 (0, 0)。"""
        self._local.crop_x = 0
        self._local.crop_y = 0

    @property
    def crop_offset(self) -> tuple[int, int]:
        """获取当前线程的裁剪偏移。"""
        return (
            getattr(self._local, "crop_x", 0),
            getattr(self._local, "crop_y", 0),
        )

    # --- 添加 trace ---

    def add_vision(self, item: VisionTraceItem) -> None:
        """添加视觉识别 trace，自动应用当前线程的 crop_offset。"""
        item.created = _normalize_created(item.created)
        ox, oy = self.crop_offset
        if ox or oy:
            item.x1 += ox
            item.y1 += oy
            item.x2 += ox
            item.y2 += oy
        with self._lock:
            self._vision.append(item)

    def add_decision(self, item: DecisionTraceItem) -> None:
        """添加决策/流转 trace。"""
        item.created = _normalize_created(item.created)
        with self._lock:
            self._decision.append(item)

    def add_timeline(self, item: TimelineTraceItem) -> None:
        """添加时间线事件 trace。"""
        item.created = _normalize_created(item.created)
        with self._lock:
            self._timeline.append(item)

    def add_perf(self, item: PerfTraceItem) -> None:
        """添加性能指标 trace。"""
        item.created = _normalize_created(item.created)
        with self._lock:
            self._perf.append(item)

    # --- 快照与清理 ---

    def snapshot(self) -> DebugTraceSnapshot:
        """获取当前所有 trace 的快照（浅拷贝，避免锁内耗时操作）。"""
        with self._lock:
            vision = list(self._vision)
            decision = list(self._decision)
            timeline = list(self._timeline)
            perf = list(self._perf)
        return DebugTraceSnapshot(
            vision_items=vision,
            decision_items=decision,
            timeline_items=timeline,
            perf_items=perf,
            created=time.time(),
        )

    def clear(self) -> None:
        """清空所有 trace 数据。"""
        with self._lock:
            self._vision.clear()
            self._decision.clear()
            self._timeline.clear()
            self._perf.clear()
