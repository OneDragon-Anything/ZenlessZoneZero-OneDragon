from __future__ import annotations

import time
from typing import TYPE_CHECKING

from one_dragon.base.controller.drag_timing import DragTiming
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_item_vision import (
    ACTION_FILL,
    ACTION_SWAP,
    ITEM_TYPE_CURRENCY,
    ITEM_TYPE_OTHER,
    BagelSlotMark,
    choose_store_action,
    identify_quality,
    identify_type,
    inspect_occupied,
)
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_search_panel import SearchPanelGuard
from zzz_od.application.bagel.bagel_search_progress import BagelSearchProgress
from zzz_od.application.bagel.bagel_slots import (
    SAFE_SLOT_CENTERS,
    SLOT_ITEM,
    inspect_safe_slots,
    result_slot_states,
    slot_occupied,
    slot_state,
    swap_visually_ok,
    transfer_visually_ok,
)
from zzz_od.application.bagel.bagel_stats import (
    QUALITY_RED,
    BagelSafeLedger,
    parse_quantity,
)

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.operation.operation_base import OperationResult
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
# 源格物品搬不动时返回的状态。节点边声明和返回值共用同一个常量：两处写错的字符串
# 不会报错，只会让框架找不到下一个节点、把「跳过这一格」静默当成整步结束。
_STATUS_SKIP_SLOT: str = '跳过不入箱的格子'
# 安全箱格子下方数量文字的纵向范围与半宽，按局内 1080p 画面。
_SAFE_QUANTITY_TOP: int = 922
_SAFE_QUANTITY_BOTTOM: int = 952
_SAFE_QUANTITY_HALF_WIDTH: int = 45


class BagelStoreSafe(BagelOperation):
    """将金币以外的结果装入安全箱，完成后保留面板供独立关闭步骤处理。"""

    STATUS_EMPTY: str = '无可入箱物品'
    STATUS_DONE: str = '已装入安全箱'
    # 保留物品搬运的前后台时序，不依赖公共拖拽默认值。
    FOREGROUND_DRAG_TIMING: DragTiming = DragTiming(
        press_wait=0.3, move_duration=0.3, release_wait=0.2,
    )
    BACKGROUND_DRAG_TIMING: DragTiming = DragTiming(
        press_wait=0.02, move_duration=0.6, release_wait=0.2,
    )
    # 拖拽后画面无变化时的重拖上限。搜索出高价值物品时游戏会先播一段加载动画，
    # 画面更新滞后于点击，一次重试不够；失败三次就把这一格记为不可入箱并跳过，
    # 不停机（金币本来就不进安全箱，别的物品也可能被游戏拒绝搬运）。
    DRAG_REPEAT_LIMIT: int = 3
    # 连续这么多件物品搬不动就不再往下磨：报局内流程失败，交给正式应用退出本局、
    # 结算后重开。一件搬不动只跳过该格；连续两件都搬不动，多半是这一局的面板或
    # 交互已经不对，继续磨只会把整局时间耗光。
    CONSECUTIVE_FAILURE_LIMIT: int = 2
    # 连续等不到稳定画面的帧数上限（每帧等待 0.3 秒，即约 3 秒）。
    # 面板刚打开、以及拖拽后物品落地都有动画，留足时间；每次发出拖拽前会清零，
    # 所以这是「一件物品一次」的预算，不会跨件累计。
    PANEL_WAIT_ROUNDS_LIMIT: int = 10
    # 无确认进展与总用时分别限制；进展不能刷新总用时。
    NO_PROGRESS_SECONDS: float = 10.0
    TOTAL_TIMEOUT_SECONDS: float = 30.0
    # 亮度和有效角标同时满足后，先留出揭示收尾时间，再用新截图复核。
    ITEM_READY_DELAY: float = 0.1

    def __init__(
        self, ctx: ZContext, blueprint_priority: bool = True,
        ledger: BagelSafeLedger | None = None,
    ) -> None:
        """按传入的优先级收集当前容器，不关闭面板，也不补做交互。

        Args:
            ctx: 运行上下文。
            blueprint_priority: 蓝图是否优先入箱。
            ledger: 本局安全箱物品账本；给定时顺带记录带出的物品，只用于统计日志。
        """
        super().__init__(ctx, op_name='贝果-装入安全箱', timeout_seconds=self.TOTAL_TIMEOUT_SECONDS)
        self.blueprint_priority: bool = blueprint_priority
        self.ledger: BagelSafeLedger | None = ledger
        self.moved: int = 0
        self.acted: bool = False
        self._pending_before: MatLike | None = None
        self._pending_source: Point | None = None
        self._pending_source_index: int | None = None
        self._pending_destination: Point | None = None
        self._pending_kind: str | None = None
        self._swap_seen: set[int] = set()
        self._unstorable: set[int] = set()
        self._consecutive_failures: int = 0
        self._drag_repeated: int = 0
        self._left_grid_waited: bool = False
        self._search_progress: BagelSearchProgress = BagelSearchProgress()
        self._progress_centers: tuple[tuple[float, float], ...] = ()
        self._result_layout_changed: bool = False
        self._finish_snapshot: str | None = None
        self._finish_frame_time: float | None = None
        self._logged_progress: str | None = None
        self._result_centers: tuple[Point, ...] = ()
        self._logged_items: dict[str, tuple[tuple[int, str, str], ...]] = {}
        self._panel_guard: SearchPanelGuard = SearchPanelGuard()
        self._panel_wait_rounds: int = 0
        self._safe_unknown_rounds: int = 0
        self._paused_usage_time: float | None = None
        self._first_pause_start_time: float | None = None

    @property
    def operation_usage_time(self) -> float:
        """暂停期间冻结用时，避免框架在处理暂停前先触发总超时。"""
        if self._paused_usage_time is not None:
            return self._paused_usage_time
        return super().operation_usage_time

    def handle_pause(self) -> None:
        """冻结用时并保留首次暂停起点，节点结束后的重复回调不能缩短暂停时长。"""
        if self._paused_usage_time is None:
            self._paused_usage_time = super().operation_usage_time
            self._first_pause_start_time = self.pause_start_time
        elif self._first_pause_start_time is not None:
            # 框架每次 _on_pause 都重写起点；恢复首次起点，供 _on_resume 完整扣除。
            self.pause_start_time = self._first_pause_start_time
        super().handle_pause()

    def handle_resume(self) -> None:
        """框架按首次起点扣除暂停时间后，再清空本轮冻结状态。"""
        self._paused_usage_time = None
        self._first_pause_start_time = None
        super().handle_resume()

    def handle_init(self) -> None:
        """每次执行清空已装入计数与待核对拖拽。"""
        super().handle_init()
        self._paused_usage_time = None
        self._first_pause_start_time = None
        self.moved = 0
        self.acted = False
        self._pending_before = None
        self._pending_source = None
        self._pending_source_index = None
        self._pending_destination = None
        self._pending_kind = None
        self._swap_seen = set()
        self._unstorable = set()
        self._consecutive_failures = 0
        self._drag_repeated = 0
        self._left_grid_waited = False
        self._search_progress = BagelSearchProgress()
        self._progress_centers = ()
        self._result_layout_changed = False
        self._finish_snapshot = None
        self._finish_frame_time = None
        self._logged_progress = None
        self._result_centers = ()
        self._logged_items.clear()
        self._panel_guard.reset()
        self._panel_wait_rounds = 0
        self._safe_unknown_rounds = 0

    def _check_search_panel(self) -> OperationRoundResult | None:
        """搜查和拖后回读共用门槛；中断优先，未知画面有界等待。

        `_panel_wait_rounds` 是「连续等不到稳定画面」的帧数，**每次发出拖拽
        前都会清零**（见 `store_next`）。之前它只在守卫通过时清零，于是开局
        等面板铺开的几帧会被一直记着，拖完一件后再等几帧就累积越过上限，
        在画面完全正常的情况下误报「搜查面板状态持续不明」。
        """
        if self.is_bagel_result():
            self._clear_pending()
            return self.round_fail(self.STATUS_DEFEATED)
        deadline = self._check_collection_deadline()
        if deadline is not None:
            return deadline
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
        elif self._observe_panel():
            centers = self._panel_guard.result_centers
            assert centers is not None
            self._result_centers = centers
            self._panel_wait_rounds = 0
            return None
        if self._result_layout_changed:
            self._clear_pending()
            return self.round_recoverable_fail('结果格位置变化，无法沿用本次搜查登记')
        self._panel_wait_rounds += 1
        if self._panel_wait_rounds < self.PANEL_WAIT_ROUNDS_LIMIT:
            return self.round_wait('等待搜查面板到位并稳定', wait=0.3)
        self._clear_pending()
        return self._give_up('搜查面板状态持续不明')

    def _observe_panel(self) -> bool:
        """按「全部拾取」按钮的位置定排数，再核对格心与画面稳定。

        小容器（公文包这类）只有一排结果格，按钮贴在那一排下方，y≈343；
        大容器（电子保险箱这类）两排，按钮被挤到 y≈501。排数认不出来时不
        猜测，先继续等下一帧。
        """
        rows = self._result_rows()
        if rows is None:
            return False
        stable = self._panel_guard.observe(self.last_screenshot, self.last_screenshot_time, rows)
        centers = self._panel_guard.result_centers
        if centers is None:
            return False
        key = tuple(point.tuple() for point in centers)
        if key != self._progress_centers:
            if self._search_progress.registered:
                self._result_layout_changed = True
                return False
            self._progress_centers = key
            self._search_progress = BagelSearchProgress()
        # 初始定位期间保留加载证据；拖后只读稳定画面，避免移动图标污染空格。
        if not self._search_progress.registered or stable:
            self._search_progress.observe(
                result_slot_states(self.last_screenshot, centers),
                self.last_screenshot_time, self.operation_usage_time,
            )
        return stable

    def _result_rows(self) -> int | None:
        """结果格排数：单行按钮在上、双行按钮在下，两者位置不重叠。"""
        if self._has('全部拾取_单行'):
            return 1
        if self._has('全部拾取_双行'):
            return 2
        return None

    def _check_collection_deadline(self) -> OperationRoundResult | None:
        """等待、拖前和拖后都检查期限，确认进展不延长总用时。"""
        elapsed = self.operation_usage_time
        if elapsed >= self.TOTAL_TIMEOUT_SECONDS:
            self._clear_pending()
            return self.round_fail(self.STATUS_TIMEOUT)
        progress_time = self._search_progress.last_progress_time
        if progress_time is not None and elapsed - progress_time >= self.NO_PROGRESS_SECONDS:
            log.warning(
                '贝果搜查连续 %.0f 秒无确认进展：%s',
                self.NO_PROGRESS_SECONDS, self._search_progress.summary(),
            )
            self._clear_pending()
            return self.round_recoverable_fail(f'搜查连续{self.NO_PROGRESS_SECONDS:.0f}秒无确认进展')
        return None

    def _finish_collection(self, status: str) -> OperationRoundResult:
        """全部格子定论且下一张新截图复核一致，才正常完成收集。"""
        progress = self._search_progress
        if not progress.registered or progress.pending or self._pending_source_index is not None:
            self._finish_snapshot = None
            self._finish_frame_time = None
            return self.round_wait('等待结果格揭示并确认', wait=0.3)
        snapshot = progress.summary()
        if self._finish_snapshot != snapshot or self._finish_frame_time is None:
            self._finish_snapshot = snapshot
            self._finish_frame_time = self.last_screenshot_time
            return self.round_wait('等待收尾前的新截图复核', wait=0.1)
        if self.last_screenshot_time <= self._finish_frame_time:
            return self.round_wait('等待收尾前的新截图复核', wait=0.1)
        self._record_safe_items()
        deadline = self._check_collection_deadline()
        if deadline is not None:
            return deadline
        for index in progress.confirmed:
            if index not in progress.handled:
                progress.mark_handled(index, '按优先级保留', self.operation_usage_time)
        log.info('贝果搜查完成：%s', progress.summary())
        return self.round_success(status, data={'moved': self.moved})

    def _wait_for_safe_slots(self) -> OperationRoundResult:
        """未知格最多额外复查三帧；等待期间保留拖拽基线，不发送输入。"""
        self._safe_unknown_rounds += 1
        if self._safe_unknown_rounds <= 3:
            return self.round_wait('安全箱格子暂不明确，等待下一帧', wait=0.3)
        self._clear_pending()
        return self.round_fail('安全箱格子状态不明，停止并保留现场')

    def _search_ready(self) -> bool:
        """搜查面板与安全箱同时可见才允许拖拽；箱子与电子保险箱标题均可。"""
        title_ok = self._has('搜查容器标题') or self._has('电子保险箱标题')
        return title_ok and self.round_by_find_area(
            self.last_screenshot, '贝果-局内', '搜查安全箱',
        ).is_success and (self._has('全部拾取_单行') or self._has('全部拾取_双行'))

    def _log_recognized_items(self, area: str, marks: list[BagelSlotMark]) -> None:
        """首次识别或格号、种类、品质变化时记录，避免等待期间重复打印。"""
        items = tuple((mark.index, mark.item_type, mark.quality) for mark in marks)
        if self._logged_items.get(area) == items:
            return
        previous = {index: (kind, quality) for index, kind, quality in self._logged_items.get(area, ())}
        current = {index: (kind, quality) for index, kind, quality in items}
        details: list[str] = []
        for index, (kind, quality) in current.items():
            if previous.get(index) == (kind, quality):
                continue
            before = previous.get(index)
            change = f'（原种类={before[0]}，品质={before[1]}）' if before else ''
            details.append(f'格 {index + 1}：种类={kind}，品质={quality}{change}')
        for index in sorted(previous.keys() - current.keys()):
            details.append(f'格 {index + 1}：不再进入本轮物品识别')
        self._logged_items[area] = items
        log.info('贝果物品识别：%s，当前 %s 格；%s', area, len(items), '；'.join(details) or '无已识别物品')

    def _ready_results(self, results: list[BagelSlotMark]) -> list[BagelSlotMark]:
        """确认结果格类型，金币记为已跳过，其他物品交给原优先级选择。"""
        ready: list[BagelSlotMark] = []
        for mark in self._search_progress.ready_items(results, self.operation_usage_time):
            if mark.item_type == ITEM_TYPE_CURRENCY:
                self._search_progress.mark_handled(
                    mark.index, '金币跳过', self.operation_usage_time,
                )
            elif mark.index not in self._swap_seen:
                ready.append(mark)
        snapshot = self._search_progress.summary()
        if snapshot != self._logged_progress:
            log.info('贝果搜查登记：%s', snapshot)
            self._logged_progress = snapshot
        return ready

    @node_from(from_name='核对入箱变化', status=_STATUS_SKIP_SLOT)
    @node_from(from_name='核对入箱变化', status='继续装入')
    @operation_node(name='逐件装入安全箱', is_start_node=True)
    def store_next(self) -> OperationRoundResult:
        """每次只拖一件并回读；装不下的留在搜索结果中。"""
        panel_result = self._check_search_panel()
        if panel_result is not None:
            return panel_result
        screen = self.last_screenshot
        states = self._search_progress.states
        # 底部文字在揭示闪光结束前就可能变亮，所有候选还必须匹配有效角标。
        # 已确认格可以先处理；角标未确认的格子即使暂时掉回空档，也不能用于收尾。
        results = inspect_occupied(
            screen,
            self._result_centers,
            [index for index, state in enumerate(states) if state == SLOT_ITEM],
        )
        self._log_recognized_items('结果区', results)
        results = self._ready_results([
            mark for mark in results if mark.index not in self._unstorable
        ])
        if not results:
            if inspect_safe_slots(screen) is None:
                return self._wait_for_safe_slots()
            self._safe_unknown_rounds = 0
            status = self.STATUS_DONE if self.moved or self.acted else self.STATUS_EMPTY
            return self._finish_collection(status)
        safe = inspect_safe_slots(screen)
        if safe is None:
            return self._wait_for_safe_slots()
        safes = inspect_occupied(screen, SAFE_SLOT_CENTERS, safe.occupied)
        self._log_recognized_items('安全箱', safes)
        choice = choose_store_action(
            results,
            safes,
            safe.empty,
            self.blueprint_priority,
        )
        if choice is None:
            self._safe_unknown_rounds = 0
            return self._finish_collection(self.STATUS_DONE)
        self._finish_snapshot = None
        self._finish_frame_time = None
        source = self._result_centers[choice.source_index]
        destination = _DEST_CENTERS[choice.kind][choice.dest_index]
        # 等待后重新截图，复核面板、亮度与角标；通过后才登记对换并发送拖拽。
        recheck = self._recheck_source(choice.source_index, choice.mark.item_type)
        if recheck is not None:
            return recheck
        current_safe = inspect_safe_slots(self.last_screenshot)
        if current_safe is None:
            return self._wait_for_safe_slots()
        self._safe_unknown_rounds = 0
        if current_safe.locked != safe.locked:
            return self.round_fail('拖拽前安全箱开放格变化，停止并保留现场')
        eligible = current_safe.empty if choice.kind == ACTION_FILL else current_safe.occupied
        if choice.dest_index not in eligible:
            return self.round_wait('目标格状态变化，重新挑选', wait=0.2)
        deadline = self._check_collection_deadline()
        if deadline is not None:
            return deadline
        if choice.kind == ACTION_SWAP:
            self._swap_seen.add(choice.source_index)
        self._pending_before = self.last_screenshot.copy()
        self._pending_source = source
        self._pending_source_index = choice.source_index
        self._pending_destination = destination
        self._pending_kind = choice.kind
        self._drag_repeated = 0
        self._left_grid_waited = False
        previous_item = next((mark for mark in safes if mark.index == choice.dest_index), None)
        destination_item = (
            f'{previous_item.quality} {previous_item.item_type}' if previous_item is not None else '空格'
        )
        log.info(
            '贝果入箱：%s %s 结果格 %s %s -> %s格 %s %s；选择时目标=%s，蓝图优先=%s',
            choice.mark.quality, choice.mark.item_type, choice.source_index + 1, source.tuple(),
            _DEST_LABEL[choice.kind], choice.dest_index + 1, destination.tuple(),
            destination_item, self.blueprint_priority,
        )
        if self.ledger is not None:
            self.ledger.start_transfer(choice.dest_index, (choice.mark.item_type, choice.mark.quality))
        self._drag_item(source, destination)
        return self.round_success('已拖拽一件', wait=0.7)

    def _recheck_source(self, source_index: int, expected_type: str) -> OperationRoundResult | None:
        """亮度和角标达标后延迟 0.1 秒，复核仍可处理才发送拖拽。

        新截图须重新通过面板检查，底部仍须有物品且角标类型保持一致。
        复核失效只等待或重新挑选，不消耗搬运重试次数。
        """
        before_time = self.last_screenshot_time
        before_center = self._result_centers[source_index]
        time.sleep(self.ITEM_READY_DELAY)
        self.screenshot()
        if self.last_screenshot_time <= before_time:
            return self.round_wait('等待拖拽前的新截图', wait=self.ITEM_READY_DELAY)
        panel_result = self._check_search_panel()
        if panel_result is not None:
            return panel_result
        source = self._result_centers[source_index]
        if source.tuple() != before_center.tuple():
            return self.round_wait('结果格位置变化，重新挑选', wait=0.2)
        if slot_state(self.last_screenshot, source) != SLOT_ITEM:
            self._search_progress.invalidate(source_index)
            return self.round_wait('源格亮度未达标，等待重新确认', wait=0.2)
        item_type = identify_type(self.last_screenshot, source)
        if item_type == ITEM_TYPE_OTHER:
            self._search_progress.invalidate(source_index)
            return self.round_wait('等待结果格有效角标', wait=0.3)
        if item_type != ITEM_TYPE_CURRENCY:
            if item_type != expected_type:
                self._search_progress.invalidate(source_index)
                return self.round_wait('源格角标类型变化，重新挑选', wait=0.2)
            return None
        give_up = self._skip_source(source_index, '金币不占安全箱')
        if give_up is not None:
            return give_up
        # 挑选就在本节点里，跳过之后留在本节点重新挑；返回带状态的成功会让框架
        # 去找「逐件装入安全箱」出发的边，找不到就当成整步结束，剩下的物品全丢。
        return self.round_wait('金币不占安全箱，改选其它物品', wait=0.2)

    def _skip_source(self, source_index: int, reason: str) -> OperationRoundResult | None:
        """记下搬不动的源格并跳过，不因此中断整局。

        一件搬不动就停机，代价远大于把它留在搜索结果里：金币本来就不进安全箱，
        其它物品也可能被游戏拒绝搬运。跳过之后继续装剩下的物品，全部跳完时由
        逐件装入安全箱按正常完成收尾。

        当场复核到金币的不算失败（金币不占安全箱，本来就不该搬），也不计入连续
        失败；其它原因才算，连续失败到上限就返回 _give_up 的结果退出本局重开。
        返回 None 表示只是跳过这一格，怎么继续由调用方决定（见 `_recheck_source`
        与 `核对入箱变化`）。
        """
        self._unstorable.add(source_index)
        self._search_progress.mark_handled(source_index, reason, self.operation_usage_time)
        source = self._result_centers[source_index]
        observed_type = identify_type(self.last_screenshot, source)
        log.info(
            '贝果入箱：结果格 %s 当场复核为 %s %s，%s；跳过该格继续',
            source_index + 1,
            identify_quality(self.last_screenshot, source),
            observed_type,
            reason,
        )
        self._clear_pending()
        if observed_type == ITEM_TYPE_CURRENCY:
            return None
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.CONSECUTIVE_FAILURE_LIMIT:
            return self._give_up(
                f'连续 {self._consecutive_failures} 件物品搬不动（{reason}），退出本局重开',
            )
        return None

    def _skip_and_reselect(self, source_index: int, reason: str) -> OperationRoundResult:
        """核对节点的跳过：回到挑选节点继续装别的物品。

        待核对数据已经清掉，留在本节点只会报「缺少入箱前后对照数据」，所以必须
        带回挑选节点的状态；节点边用同一个常量声明，见 `_STATUS_SKIP_SLOT`。
        """
        give_up = self._skip_source(source_index, reason)
        if give_up is not None:
            return give_up
        return self.round_success(_STATUS_SKIP_SLOT, wait=0.2)

    def _give_up(self, reason: str) -> OperationRoundResult:
        """本步无法安全继续：报局内流程失败，由正式应用退出本局、结算后重开。

        返回的状态必须是 `贝果局内流程失败`：正式应用只对它有「退出本局再重开」的
        分支，其它自造状态会一路走到任务结束。原因放进 data，日志和现场截图都带上。
        退出时游戏只保留安全箱物资，比把整个任务停在这里更划算；整体重试次数照常扣。
        """
        return self.round_fail(self.STATUS_ROUND_FAILED, data=reason)

    def _clear_pending(self) -> None:
        """丢掉这一次拖拽的前后对照；未确认入箱的账本登记一并撤销。"""
        if self.ledger is not None:
            self.ledger.cancel_transfer()
        self._pending_before = None
        self._pending_source = None
        self._pending_source_index = None
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
        source_index = self._pending_source_index
        destination = self._pending_destination
        kind = self._pending_kind
        if (before is None or source is None or source_index is None
                or destination is None or kind is None):
            return self._give_up('缺少入箱前后对照数据')
        if self._result_centers[source_index].tuple() != source.tuple():
            return self._give_up('拖拽后结果格位置变化，无法核对原次搬运')
        safe = inspect_safe_slots(self.last_screenshot)
        if safe is None:
            return self._wait_for_safe_slots()
        self._safe_unknown_rounds = 0
        safe_before = inspect_safe_slots(before)
        destination_index = next(
            (index for index, center in enumerate(SAFE_SLOT_CENTERS)
             if center.tuple() == destination.tuple()), None,
        )
        if (safe_before is None or destination_index is None
                or safe.locked != safe_before.locked or destination_index in safe.locked):
            return self.round_fail('无法核对拖拽目标的开放状态，停止并保留现场')
        eligible_before = safe_before.empty if kind == ACTION_FILL else safe_before.occupied
        if destination_index not in eligible_before:
            return self.round_fail('拖拽前目标格状态不符，停止并保留现场')
        if kind == ACTION_SWAP and destination_index not in safe.occupied:
            return self.round_fail('对换后安全箱目标格不再占用，停止并保留现场')
        if destination_index in safe.occupied and self._drag_visually_ok(kind, before, source, destination):
            self._confirm_ledger_transfer()
            self._clear_pending()
            self._drag_repeated = 0
            self._left_grid_waited = False
            self._consecutive_failures = 0
            if kind == ACTION_FILL:
                self.moved += 1
            self.acted = True
            return self.round_success('继续装入', wait=0.2)
        after = self.last_screenshot
        source_now = slot_occupied(after, source)
        dest_now = destination_index in safe.occupied
        if (
            kind == ACTION_FILL
            and source_now
            and not dest_now
            and not slot_occupied(before, destination)
        ):
            # 源格还在、目标格仍空，且拖前目标格确实是空的：这次拖拽确实没生效。
            # 物品加载慢时画面滞后于点击，多给几次机会而不是一次就放弃。
            # 重试期间目标格保持不变，避免把物品拖到计划外位置。
            if self._drag_repeated < self.DRAG_REPEAT_LIMIT:
                self._drag_repeated += 1
                self._pending_before = after.copy()
                self._drag_item(source, destination)
                return self.round_wait(
                    f'入箱画面无变化，第 {self._drag_repeated} 次重拖', wait=0.7,
                )
            # 重拖预算用完画面仍无变化：这一格游戏就是不让搬（金币直接进携带货币、
            # 不占安全箱格；别的物品也可能被拒绝），再拖也是一样的结果。跳过它继续装
            # 剩下的物品，而不是停掉整局。
            return self._skip_and_reselect(
                source_index,
                f'首次拖拽和 {self.DRAG_REPEAT_LIMIT} 次重拖后源格仍未入箱',
            )
        if kind == ACTION_FILL and dest_now and not slot_occupied(before, destination):
            # 面板已通过稳定检查，目标格由空变有即可确认填空成功。
            # 源格可能误识别为占用，不能因此对已占用的目标再次拖拽。
            self._confirm_ledger_transfer()
            self._clear_pending()
            self._drag_repeated = 0
            self._left_grid_waited = False
            self._consecutive_failures = 0
            self.moved += 1
            self.acted = True
            return self.round_success('继续装入', wait=0.2)
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
            return self._give_up('离开了搜索格但没进安全箱')
        if kind == ACTION_SWAP and source_now and self._drag_repeated < 1:
            self._drag_repeated += 1
            self._pending_before = after.copy()
            self._drag_item(source, destination)
            return self.round_wait('对换画面未确认，再拖一次', wait=0.7)
        if kind == ACTION_SWAP:
            # 对换也确认不了：这一格换不进安全箱。跳过它去看别的候选，不停机。
            return self._skip_and_reselect(source_index, '对换重拖后两格外观仍未变化')
        self._clear_pending()
        return self._give_up('入箱画面无变化，源格和目标格都没动')

    def _confirm_ledger_transfer(self) -> None:
        """入箱已确认，账本里该格换成拖入的物品。"""
        source_index = self._pending_source_index
        if source_index is not None:
            reason = '已对换' if self._pending_kind == ACTION_SWAP else '已入箱'
            self._search_progress.mark_handled(
                source_index, reason, self.operation_usage_time, transferred=True,
            )
        if self.ledger is not None:
            self.ledger.confirm_transfer()

    def after_operation_done(self, result: OperationResult) -> None:
        """超时和人工结束也撤销未确认的账本登记，已入箱记录保持不变。"""
        self._clear_pending()
        if not result.success:
            log.warning('贝果搜查未完成：%s；%s', result.status, self._search_progress.summary())
        super().after_operation_done(result)

    def _record_safe_items(self) -> None:
        """记下装箱结束时安全箱各格的类型和品质，只读红色物品的数量；只用于统计日志。"""
        if self.ledger is None:
            return
        try:
            safe = inspect_safe_slots(self.last_screenshot)
            if safe is None:
                return
            items: dict[int, tuple[str, str, int | None]] = {}
            for mark in inspect_occupied(self.last_screenshot, SAFE_SLOT_CENTERS, safe.occupied):
                if mark.quality != QUALITY_RED:
                    items[mark.index] = (mark.item_type, mark.quality, None)
                    continue
                rect = Rect(
                    mark.center.x - _SAFE_QUANTITY_HALF_WIDTH, _SAFE_QUANTITY_TOP,
                    mark.center.x + _SAFE_QUANTITY_HALF_WIDTH, _SAFE_QUANTITY_BOTTOM,
                )
                texts = self.ctx.ocr_service.get_ocr_result_list(image=self.last_screenshot, rect=rect)
                quantity = parse_quantity(''.join(item.data for item in texts))
                items[mark.index] = (mark.item_type, mark.quality, quantity)
            self.ledger.slot_items = items
        except Exception:
            log.error('记录安全箱物品失败，本次不计入统计', exc_info=True)

    def _drag_item(self, source: Point, destination: Point) -> None:
        """先按住再移动，给游戏时间抓起物品，避免拖成结果列表滚动。"""
        self._panel_guard.reset()
        # 每次发出拖拽都重新给一次「等面板稳住」的预算：开局等面板铺开、
        # 拖后等物品落地是两段独立动画，不能把前者的帧数算进后者的上限。
        self._panel_wait_rounds = 0
        timing = (
            self.BACKGROUND_DRAG_TIMING
            if self.ctx.controller.background_mode
            else self.FOREGROUND_DRAG_TIMING
        )
        self.ctx.controller.drag_to(
            end=destination, start=source, timing=timing,
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
        """箱子或电子保险箱标题任一可见即仍在搜查面板。"""
        return self._has('搜查容器标题') or self._has('电子保险箱标题')
