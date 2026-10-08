from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_item_vision import (
    ACTION_FILL,
    ACTION_SWAP,
    BagelSlotMark,
    choose_store_action,
    inspect_occupied,
)
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_search_panel import SearchPanelGuard
from zzz_od.application.bagel.bagel_slots import (
    RESULT_SLOT_CENTERS,
    SAFE_SLOT_CENTERS,
    inspect_safe_slots,
    slot_crop,
    slot_occupied,
    swap_visually_ok,
    transfer_visually_ok,
)

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext

_DEST_CENTERS: dict[str, tuple[Point, ...]] = {
    ACTION_FILL: SAFE_SLOT_CENTERS,
    ACTION_SWAP: SAFE_SLOT_CENTERS,
}
_DEST_LABEL: dict[str, str] = {
    ACTION_FILL: '安全箱',
    ACTION_SWAP: '安全箱对换',
}


class BagelStoreSafe(BagelOperation):
    """将金币以外的结果装入安全箱，完成后保留面板供独立关闭步骤处理。"""

    STATUS_EMPTY: str = '无可入箱物品'
    STATUS_DONE: str = '已装入安全箱'

    def __init__(self, ctx: ZContext) -> None:
        """只收集当前容器，不关闭面板，也不补做交互。"""
        super().__init__(ctx, op_name='贝果-装入安全箱', timeout_seconds=90)
        self.moved: int = 0
        self.acted: bool = False
        self._pending_before: MatLike | None = None
        self._pending_source: Point | None = None
        self._pending_destination: Point | None = None
        self._pending_kind: str | None = None
        self._swap_seen: set[int] = set()
        self._drag_repeated: bool = False
        self._left_grid_waited: bool = False
        self._search_frame: MatLike | None = None
        self._panel_guard: SearchPanelGuard = SearchPanelGuard()
        self._panel_wait_rounds: int = 0
        self._safe_unknown_rounds: int = 0

    def handle_init(self) -> None:
        """每次执行清空已装入计数与待核对拖拽。"""
        super().handle_init()
        self.moved = 0
        self.acted = False
        self._pending_before = None
        self._pending_source = None
        self._pending_destination = None
        self._pending_kind = None
        self._swap_seen = set()
        self._drag_repeated = False
        self._left_grid_waited = False
        self._search_frame = None
        self._panel_guard.reset()
        self._panel_wait_rounds = 0
        self._safe_unknown_rounds = 0

    def _check_search_panel(self) -> OperationRoundResult | None:
        """搜查和拖后回读共用门槛；中断优先，未知画面有界等待。"""
        if self.is_bagel_result():
            self._clear_pending()
            return self.round_fail(self.STATUS_DEFEATED)
        if not self._search_ready():
            self._panel_guard.reset()
            if (not self._has_search_title()
                    and not self.round_by_find_area(
                        self.last_screenshot, '贝果-局内', '大保险解锁提示',
                    ).is_success
                    and self.round_by_find_area(
                        self.last_screenshot, '战斗画面', '按键-普通攻击',
                    ).is_success):
                self._clear_pending()
                return self.round_fail(self.STATUS_INTERRUPTED)
        elif self._panel_guard.observe(self.last_screenshot, self.last_screenshot_time):
            self._panel_wait_rounds = 0
            return None
        self._search_frame = None
        self._panel_wait_rounds += 1
        if self._panel_wait_rounds < 6:
            return self.round_wait('等待搜查面板到位并稳定', wait=0.3)
        self._clear_pending()
        return self.round_fail('搜查面板状态持续不明，停止并保留现场')

    def _wait_for_safe_slots(self) -> OperationRoundResult:
        """未知格最多额外复查三帧；等待期间保留拖拽基线，不发送输入。"""
        self._safe_unknown_rounds += 1
        if self._safe_unknown_rounds <= 3:
            return self.round_wait('安全箱格子暂不明确，等待下一帧', wait=0.3)
        self._clear_pending()
        return self.round_fail('安全箱格子状态不明，停止并保留现场')

    def _search_ready(self) -> bool:
        """搜查面板与安全箱同时可见才允许拖拽；武备箱与电子保险箱标题均可。"""
        title_ok = (
            self.round_by_find_area(
                self.last_screenshot, '贝果-局内', '搜查容器标题',
            ).is_success
            or self.round_by_find_area(
                self.last_screenshot, '贝果-局内', '电子保险箱标题',
            ).is_success
        )
        return title_ok and self.round_by_find_area(
            self.last_screenshot, '贝果-局内', '搜查安全箱',
        ).is_success and (self._search_complete() or self.round_by_find_area(
            self.last_screenshot, '贝果-局内', '搜查进行中',
        ).is_success)

    def _search_complete(self) -> bool:
        """只有搜索结果文字出现后才允许关闭面板。"""
        return self.round_by_find_area(
            self.last_screenshot, '贝果-局内', '搜查完成',
        ).is_success

    def _stable_results(self, results: list[BagelSlotMark]) -> list[BagelSlotMark]:
        """搜查进行中只处理连续两帧外观稳定的已揭示格。"""
        previous = self._search_frame
        current = self.last_screenshot
        self._search_frame = current.copy()
        if previous is None:
            return []
        stable: list[BagelSlotMark] = []
        for mark in results:
            before = slot_crop(previous, mark.center)
            after = slot_crop(current, mark.center)
            if (before is not None and after is not None and before.shape == after.shape
                    and slot_occupied(previous, mark.center)
                    and float(abs(before.astype('float32') - after.astype('float32')).mean()) < 4):
                stable.append(mark)
        return stable

    @node_from(from_name='核对入箱变化', status='继续装入')
    @operation_node(name='逐件装入安全箱', is_start_node=True)
    def store_next(self) -> OperationRoundResult:
        """每次只拖一件并回读；装不下的留在搜索结果中。"""
        panel_result = self._check_search_panel()
        if panel_result is not None:
            return panel_result
        screen = self.last_screenshot
        results = inspect_occupied(screen, RESULT_SLOT_CENTERS)
        if not self._search_complete():
            results = self._stable_results(results)
        if not results:
            if not self._search_complete():
                return self.round_wait('等待新的搜查结果', wait=0.3)
            if inspect_safe_slots(screen) is None:
                return self._wait_for_safe_slots()
            self._safe_unknown_rounds = 0
            status = self.STATUS_DONE if self.moved or self.acted else self.STATUS_EMPTY
            return self.round_success(status, data={'moved': self.moved})
        safe = inspect_safe_slots(screen)
        if safe is None:
            return self._wait_for_safe_slots()
        self._safe_unknown_rounds = 0
        choice = choose_store_action(
            results,
            [mark for mark in inspect_occupied(screen, SAFE_SLOT_CENTERS) if mark.index in safe.occupied],
            safe.empty,
        )
        if choice is None:
            if not self._search_complete():
                return self.round_wait('等待新的搜查结果', wait=0.3)
            return self.round_success(self.STATUS_DONE, data={'moved': self.moved})
        if choice.kind == ACTION_SWAP:
            if not self._search_complete():
                return self.round_wait('等待搜索完成后核对对换', wait=0.3)
            if choice.source_index in self._swap_seen:
                log.info(
                    '贝果入箱：结果格 %s 已对换，不再将换出的物品换回',
                    choice.source_index + 1,
                )
                return self.round_success(self.STATUS_DONE, data={'moved': self.moved})
            self._swap_seen.add(choice.source_index)
        source = RESULT_SLOT_CENTERS[choice.source_index]
        destination = _DEST_CENTERS[choice.kind][choice.dest_index]
        self._pending_before = screen.copy()
        self._pending_source = source
        self._pending_destination = destination
        self._pending_kind = choice.kind
        self._drag_repeated = False
        self._left_grid_waited = False
        log.info(
            '贝果入箱：%s %s 结果格 %s -> %s格 %s',
            choice.mark.quality,
            choice.mark.item_type,
            choice.source_index + 1,
            _DEST_LABEL[choice.kind],
            choice.dest_index + 1,
        )
        self._drag_item(source, destination)
        return self.round_success('已拖拽一件', wait=0.7)

    def _clear_pending(self) -> None:
        """丢掉这一次拖拽的前后对照。"""
        self._pending_before = None
        self._pending_source = None
        self._pending_destination = None
        self._pending_kind = None

    @node_from(from_name='逐件装入安全箱', status='已拖拽一件')
    @operation_node(name='核对入箱变化')
    def confirm_transfer(self) -> OperationRoundResult:
        """按填空或对换核对画面变化。源格还在就再拖一次；离开搜索格却没进安全箱则另说。"""
        panel_result = self._check_search_panel()
        if panel_result is not None:
            return panel_result
        before = self._pending_before
        source = self._pending_source
        destination = self._pending_destination
        kind = self._pending_kind
        if before is None or source is None or destination is None or kind is None:
            return self.round_fail('缺少入箱前后对照数据')
        safe = inspect_safe_slots(self.last_screenshot)
        destination_index = SAFE_SLOT_CENTERS.index(destination)
        if safe is None:
            return self._wait_for_safe_slots()
        self._safe_unknown_rounds = 0
        if destination_index in safe.locked:
            self._clear_pending()
            return self.round_fail('入箱后安全箱格子状态不明或目标已锁定，停止并保留现场')
        if self._drag_visually_ok(kind, before, source, destination):
            self._clear_pending()
            self._drag_repeated = False
            self._left_grid_waited = False
            if kind == ACTION_FILL:
                self.moved += 1
            self.acted = True
            return self.round_success('继续装入', wait=0.2)
        after = self.last_screenshot
        source_now = slot_occupied(after, source)
        dest_now = slot_occupied(after, destination)
        if (
            kind == ACTION_FILL
            and slot_occupied(before, source)
            and not source_now
            and not dest_now
        ):
            if not self._left_grid_waited:
                self._left_grid_waited = True
                return self.round_wait('离开了搜索格，再看一帧', wait=0.4)
            self._clear_pending()
            return self.round_fail('离开了搜索格但没进安全箱，停止并保留现场')
        if source_now and not self._drag_repeated:
            self._drag_repeated = True
            self._pending_before = after.copy()
            self._drag_item(source, destination)
            return self.round_wait('入箱画面无变化，再拖一次', wait=0.7)
        self._clear_pending()
        return self.round_fail('入箱画面无变化，停止并保留现场')

    def _drag_item(self, source: Point, destination: Point) -> None:
        """先按住再移动，给游戏时间抓起物品，避免拖成结果列表滚动。"""
        self._panel_guard.reset()
        self.ctx.controller.drag_to(
            end=destination, start=source, duration=0.8, press_time=0.1,
        )

    def _drag_visually_ok(
        self,
        kind: str,
        before: MatLike,
        source: Point,
        destination: Point,
    ) -> bool:
        """填空看目标格空变有；对换看两边都占用且外观都变。"""
        after = self.last_screenshot
        if kind == ACTION_SWAP:
            return swap_visually_ok(before, after, source, destination)
        return transfer_visually_ok(before, after, source, destination)

    def _has_search_title(self) -> bool:
        """武备箱或电子保险箱标题任一可见即仍在搜查面板。"""
        return (
            self.round_by_find_area(
                self.last_screenshot, '贝果-局内', '搜查容器标题',
            ).is_success
            or self.round_by_find_area(
                self.last_screenshot, '贝果-局内', '电子保险箱标题',
            ).is_success
        )
