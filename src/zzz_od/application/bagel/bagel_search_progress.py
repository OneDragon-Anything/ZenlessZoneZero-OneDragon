"""保留一次搜查内的逐格观察，单帧变空不能撤销已登记的揭示任务。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zzz_od.application.bagel.bagel_item_vision import ITEM_TYPE_OTHER
from zzz_od.application.bagel.bagel_slots import (
    SLOT_EMPTY,
    SLOT_ITEM,
    SLOT_LOADING,
    SLOT_REVEALING,
)

if TYPE_CHECKING:
    from zzz_od.application.bagel.bagel_item_vision import BagelSlotMark


class BagelSearchProgress:
    """只在同一组格心的新截图上更新；输入动作与面板定位由收集操作负责。"""

    def __init__(self) -> None:
        """每次收集独立登记，不跨容器复用。"""
        self.states: tuple[str | None, ...] = ()
        self.required: set[int] = set()
        self.confirmed: dict[int, tuple[str, str]] = {}
        self.handled: dict[int, str] = {}
        self.last_progress_time: float | None = None
        self.frame_time: float | None = None
        self._frames: int = 0
        self._empty_frames: list[int] = []
        self._mark_candidates: dict[int, tuple[str, str]] = {}
        self._mark_frame_time: float | None = None
        self._confirmed_once: set[int] = set()

    @property
    def registered(self) -> bool:
        """初始登记至少使用两张不同时间的截图。"""
        return self._frames >= 2

    def observe(self, states: list[str | None], frame_time: float, elapsed: float) -> None:
        """登记加载证据；已判空格的单帧异常先阻止结束，再观察是否持续。"""
        if self.frame_time is not None and frame_time <= self.frame_time:
            return
        if self.states and len(states) != len(self.states):
            raise ValueError('结果格数量变化，不能沿用原搜查登记')
        if not self.states:
            self._empty_frames = [0] * len(states)
        was_registered = self.registered
        previous = self.states
        active = (SLOT_LOADING, SLOT_REVEALING, SLOT_ITEM)
        for index, state in enumerate(states):
            if index in self.handled:
                continue
            self._empty_frames[index] = min(2, self._empty_frames[index] + 1) if state == SLOT_EMPTY else 0
            # 开箱阶段保留任一帧的加载证据；已登记为空的格子要持续异常才升为待确认。
            if state in active and (
                not was_registered or previous[index] in active
            ):
                self.required.add(index)
            if state != SLOT_ITEM:
                self.confirmed.pop(index, None)
                self._mark_candidates.pop(index, None)
        self.states = tuple(states)
        self.frame_time = frame_time
        self._frames += 1
        if not was_registered and self.registered:
            self.last_progress_time = elapsed

    def ready_items(self, marks: list[BagelSlotMark], elapsed: float) -> list[BagelSlotMark]:
        """两张新截图的类型和品质一致才确认；重复确认同一格不刷新计时。"""
        if not self.registered or self.frame_time == self._mark_frame_time:
            return []
        current: dict[int, tuple[str, str]] = {}
        ready: list[BagelSlotMark] = []
        for mark in marks:
            if mark.index in self.handled or self.states[mark.index] != SLOT_ITEM:
                continue
            if mark.item_type == ITEM_TYPE_OTHER:
                continue
            identity = (mark.item_type, mark.quality)
            current[mark.index] = identity
            if self._mark_candidates.get(mark.index) != identity:
                self.confirmed.pop(mark.index, None)
                continue
            self.required.add(mark.index)
            self.confirmed[mark.index] = identity
            if mark.index not in self._confirmed_once:
                self._confirmed_once.add(mark.index)
                self.last_progress_time = elapsed
            ready.append(mark)
        for index in tuple(self.confirmed):
            if index not in current and index not in self.handled:
                self.confirmed.pop(index)
        self._mark_candidates = current
        self._mark_frame_time = self.frame_time
        return ready

    def invalidate(self, index: int) -> None:
        """拖拽前复核失效后重新确认，保留必须揭示的登记。"""
        self.required.add(index)
        self.confirmed.pop(index, None)
        self._mark_candidates.pop(index, None)

    def mark_handled(self, index: int, reason: str, elapsed: float, transferred: bool = False) -> None:
        """记录已核对的搬运或明确跳过；只有搬运成功才另计进展。"""
        if index in self.handled:
            return
        self.handled[index] = reason
        if transferred:
            self.last_progress_time = elapsed

    @property
    def pending(self) -> tuple[int, ...]:
        """返回不能用于正常收尾的格号，包括暂记空格的未复核变化。"""
        return tuple(
            index for index, state in enumerate(self.states)
            if index not in self.handled and (
                not self.registered
                or (index in self.required and (
                    index not in self.confirmed or state != SLOT_ITEM
                ))
                or (index not in self.required and self._empty_frames[index] < 2)
            )
        )

    def summary(self) -> str:
        """输出逐格观察和处理结果，兼作收尾两帧的一致性检查。"""
        slots: list[str] = []
        pending = set(self.pending)
        for index, state in enumerate(self.states):
            if index in self.handled:
                detail = self.handled[index]
            elif index in self.confirmed and index not in pending:
                kind, quality = self.confirmed[index]
                detail = f'已确认({quality} {kind})'
            elif index in pending:
                detail = f'待确认({state or "未知"})'
            else:
                detail = '空'
            slots.append(f'{index + 1}={detail}')
        return '；'.join(slots) or '尚未登记'
