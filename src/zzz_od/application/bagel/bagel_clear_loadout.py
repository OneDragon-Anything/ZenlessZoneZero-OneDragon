from __future__ import annotations

import time
from typing import TYPE_CHECKING

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_screen import (
    complete_loadout,
    empty_capacity,
    parse_capacity_pair,
    prepare_detail_state,
    read_area,
    read_loadout,
    zero_loadout,
)
from zzz_od.application.bagel.bagel_store_carried import BagelStoreCarried
from zzz_od.application.bagel.bagel_transfer import (
    BagelTransferOperation,
    carried_slot_state,
)

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


# 只定位右侧已装备槽；左侧仓储候选列表不是清空对象。
LOADOUT_GROUPS: tuple[tuple[str, tuple[Point, ...]], ...] = (
    ('武备价值', (Point(1360, 306), Point(1360, 519), Point(1360, 727))),
    ('装备价值', (Point(1520, 300), Point(1630, 300), Point(1740, 300))),
    ('道具价值', (Point(1546, 518), Point(1710, 518), Point(1546, 650), Point(1710, 650))),
)
LOADOUT_CENTERS: tuple[Point, ...] = tuple(center for _, centers in LOADOUT_GROUPS for center in centers)
# 候选列表与备战面板之间的空白，不点击详情内的搬运或出售按钮。
DETAIL_DISMISS_POINT: Point = Point(950, 540)
BACKPACK_SLOT_INDEX: int = 5
MAX_UNLOAD_RETRIES: int = 3


class BagelClearLoadout(BagelTransferOperation):
    """从备战清空内容物及已装备物品，成功时仍停在零携带备战。"""

    def __init__(self, ctx: ZContext) -> None:
        """先清容器再卸装备，保留队伍，不调用结算出售。"""
        super().__init__(ctx, op_name='贝果-清空启动战备')
        self.required_slots: int = 0
        self.viewing_backpack: bool = False
        self.pending_center: Point | None = None
        self.before_counts: tuple[tuple[int, int], tuple[int, int]] | None = None
        self.before_states: tuple[bool, ...] = ()
        self.unload_retries: int = 0
        self.unload_generation: int = 0
        self.detail_close_attempts: int = 0

    def handle_init(self) -> None:
        """清除上次卸装的基线。"""
        super().handle_init()
        self.required_slots = 0
        self.viewing_backpack = False
        self.pending_center = None
        self.before_counts = None
        self.before_states = ()
        self.unload_retries = 0
        self.unload_generation = 0
        self.detail_close_attempts = 0

    def at_prepare(self) -> bool:
        """同时核对两个备战按钮，防止在仓储库存区使用装备槽坐标。"""
        return all(self.round_by_find_area(self.last_screenshot, '贝果-备战', name).is_success
                   for name in ('预设组合', '前往空洞'))

    def _wait_unload(
        self, reason: str, *, unknown: bool = False, wait: float = 0.5,
    ) -> OperationRoundResult:
        """详情、未知状态和未生效共用本次双击预算，不因关详情而重新计时。"""
        if not self.pending:
            return self.read_again(reason)
        if unknown:
            self.read_misses += 1
            if self.read_misses >= 5:
                return self.transfer_fail(reason)
        if self.pending_checks >= 10 or time.monotonic() - self.pending_started >= 5:
            return self.transfer_fail(reason)
        return self.round_wait(reason, wait=wait)

    def _require_clear_prepare(self) -> OperationRoundResult | None:
        """详情出现时限次点击空白处，遮挡或过渡帧不能参与槽位识别。"""
        generation = self.pause_generation
        if not self.at_prepare():
            self._stable_image = None
            return self._wait_unload('未识别备战主画面', unknown=True)
        detail = prepare_detail_state(self.ctx, self.last_screenshot)
        if detail is False:
            return None
        self._stable_image = None
        if detail is None:
            return self._wait_unload('无法确认备战无遮挡', unknown=True)
        if self.pending and self.unload_generation != self.pause_generation:
            return self.transfer_fail('暂停后详情仍在，只核验结果，不补发关闭或双击')
        if self.detail_close_attempts >= 2:
            return self.transfer_fail('点击空白处2次后详情仍未关闭')
        result = self._wait_unload('等待关闭物品详情', unknown=True, wait=0)
        if result.is_fail:
            return result
        if generation != self.pause_generation or not self.ctx.run_context.is_context_running:
            return self.round_wait('等待恢复后重新识别详情', wait=0.5)
        self.detail_close_attempts += 1
        if not self.ctx.controller.click(DETAIL_DISMISS_POINT, press_time=0.08):
            return self.transfer_fail('点击空白处关闭详情失败')
        return self.round_wait('已点击空白处，等待详情关闭', wait=0.5)

    @operation_node(name='核对启动携带', is_start_node=True)
    def inspect_loadout(self) -> OperationRoundResult:
        """识别完整五项及装备槽，决定是否需要清空。"""
        result = self._require_clear_prepare()
        if result is not None:
            return result
        values = read_loadout(self.ctx, self.last_screenshot)
        self.observation = f'五项携带 {values}'
        if not complete_loadout(values):
            self._stable_image = None
            return self.read_again(f'五项携带识别不完整 {values}')
        states = [carried_slot_state(self.last_screenshot, center) for center in LOADOUT_CENTERS]
        if None in states:
            self._stable_image = None
            return self.read_again('无法完整识别已装备槽位')
        # 空槽图案和物品图标会持续闪动；按完整读数及各槽占用状态判断稳定。
        if not self.stable_slots((), (*values.values(), *states)):
            return self.read_again('等待备战格子稳定')
        self.required_slots = sum(state is True for state in states)
        self.read_misses = 0
        if zero_loadout(values):
            if any(states):
                return self.transfer_fail('五项为零但槽位仍有物品')
            return self.round_success('已是零携带')
        if all(parse_capacity_pair(values[name])[0] == 0 for name in ('背包数量', '安全箱数量')):
            return self.round_success('背包安全箱已空')
        return self.round_success('需要清空')

    @node_from(from_name='核对启动携带', status='需要清空')
    @operation_node(name='打开备战仓库', timeout_seconds=20)
    def open_warehouse(self) -> OperationRoundResult:
        """先切回背包视图，再识别前往仓库文字，按钮只点击一次。"""
        if self.round_by_find_area(self.last_screenshot, '贝果-仓库', '放入仓库').is_success:
            return self.round_success()
        if not self.at_prepare():
            return self.read_again('等待备战仓库打开')
        if self.node_clicked:
            return self.read_again('已点击前往仓库，等待切换')
        if self.round_by_ocr(self.last_screenshot, '前往仓库', lcs_percent=1).is_success:
            result = self.round_by_ocr_and_click(
                self.last_screenshot, '前往仓库', lcs_percent=1,
                success_wait=0.5, retry_wait=0.5,
            )
            if result.is_success:
                self.node_clicked = True
                self.read_misses = 0
                return self.round_wait('等待备战仓库', wait=0.5)
            return result
        if not self.viewing_backpack:
            self.viewing_backpack = True
            # 已核对备战，数量区域无匹配文字，直接点既有区域切换视图。
            result = self.round_by_click_area('贝果-备战', '背包数量')
            if result.is_success:
                self.node_clicked = False
                return self.round_wait('切换到备战背包视图', wait=0.5)
            return self.transfer_fail('无法打开备战背包视图')
        return self.read_again('未识别前往仓库')

    @node_from(from_name='打开备战仓库')
    @operation_node(name='转存背包安全箱', screenshot_before_round=False)
    def store_contents(self) -> OperationRoundResult:
        """内容物清空后，确认仓库剩余位置足以接收所有已装备槽。"""
        result = BagelStoreCarried(self.ctx).execute()
        self.screenshot()
        if not result.success:
            return self.round_by_op_result(result)
        self.moved += result.data['moved']
        used, capacity = result.data['warehouse']
        if capacity - used < self.required_slots:
            self.screenshot()
            return self.transfer_fail(f'仓库空位不足 {used}/{capacity}，尚有 {self.required_slots} 格装备待卸')
        return self.round_success()

    @node_from(from_name='转存背包安全箱')
    @operation_node(name='仓库返回备战', timeout_seconds=20)
    def return_prepare(self) -> OperationRoundResult:
        """备战仓库走左上返回，不使用结算的返回研究站。"""
        if self.at_prepare():
            self.read_misses = 0
            return self.round_success()
        if not self.round_by_find_area(self.last_screenshot, '贝果-仓库', '放入仓库').is_success:
            return self.read_again('等待仓库返回备战')
        if self.node_clicked:
            return self.read_again('等待备战画面')
        result = self.round_by_click_area('菜单', '返回')
        if result.is_success:
            self.node_clicked = True
            return self.round_wait('已点击返回备战', wait=0.5)
        return result

    @node_from(from_name='核对启动携带', status='背包安全箱已空')
    @node_from(from_name='仓库返回备战')
    @operation_node(name='逐格卸下战备')
    def unload_next(self) -> OperationRoundResult:
        """先关闭详情，逐格核验占用；全部卸完后才重新读取三个价值。"""
        if self.pending:
            self.pending_checks += 1
        result = self._require_clear_prepare()
        if result is not None:
            return result
        texts = {name: read_area(self.ctx, self.last_screenshot, '贝果-备战', name)
                 for name in ('背包数量', '安全箱数量')}
        self.observation = f'容器读数 {texts}'
        backpack = parse_capacity_pair(texts['背包数量'])
        safe = parse_capacity_pair(texts['安全箱数量'])
        if backpack is None or safe is None:
            self._stable_image = None
            return self._wait_unload('无法完整核对背包和安全箱', unknown=True)
        if backpack[0] != 0 or safe[0] != 0:
            return self.transfer_fail('卸装时背包或安全箱出现物资')
        if not all(empty_capacity(text) for text in texts.values()):
            self._stable_image = None
            return self._wait_unload('容器零占用读数不明确', unknown=True)
        counts = (backpack, safe)
        states = tuple(carried_slot_state(self.last_screenshot, center) for center in LOADOUT_CENTERS)
        self.observation += f'，槽位占用 {states}'
        if None in states:
            self._stable_image = None
            return self._wait_unload('卸装槽位状态不清', unknown=True)
        values: dict[str, str] = {}
        if not any(states):
            values = read_loadout(self.ctx, self.last_screenshot)
            self.observation += f'，五项携带 {values}'
            if (not complete_loadout(values)
                    or parse_capacity_pair(values['背包数量']) != backpack
                    or parse_capacity_pair(values['安全箱数量']) != safe):
                self._stable_image = None
                return self._wait_unload('无法完整核对最终五项携带', unknown=True)
        # 图标会闪动；稳定判据只用容器读数、槽位占用及最终五项读数。
        if not self.stable_slots((), (*counts, *states, *values.values())):
            return self._wait_unload('等待卸装结果稳定', unknown=True)
        self.read_misses = 0
        if self.pending:
            if self.pending_center is None or self.before_counts is None:
                return self.transfer_fail('缺少待核验槽位或容器基准')
            pending_index = LOADOUT_CENTERS.index(self.pending_center)
            if any(state != self.before_states[index] for index, state in enumerate(states) if index != pending_index):
                return self.transfer_fail('卸装时其他槽位占用发生变化')
            if states[pending_index]:
                if counts != self.before_counts:
                    return self.transfer_fail('原装备仍在但容器数量或容量发生变化')
                result = self._wait_unload('双击后原装备槽仍有物品')
                if (result.is_fail and self.unload_retries < MAX_UNLOAD_RETRIES
                        and self.unload_generation == self.pause_generation):
                    self.unload_retries += 1
                    self.detail_close_attempts = 0
                    label = self.source_label.split('（重试', 1)[0]
                    return self.double_click_item(
                        self.pending_center, f'{label}（重试 {self.unload_retries}/{MAX_UNLOAD_RETRIES}）',
                    )
                return result
            before_backpack, before_safe = self.before_counts
            backpack_valid = (backpack[1] <= before_backpack[1] if pending_index == BACKPACK_SLOT_INDEX
                              else backpack == before_backpack)
            if safe != before_safe or not backpack_valid:
                return self.transfer_fail(f'卸装后容器容量变化异常 {self.before_counts} -> {counts}')
            self.finish_transfer()
        if not any(states):
            if not zero_loadout(values):
                return self.transfer_fail(f'槽位已空但五项未归零 {values}')
            return self.round_success('战备已全部清空', data={'moved': self.moved})
        offset = 0
        for group, centers in LOADOUT_GROUPS:
            for index, center in enumerate(centers):
                if states[offset + index]:
                    self.pending_center = center
                    self.before_counts = counts
                    self.before_states = states
                    self.unload_retries = 0
                    self.unload_generation = self.pause_generation
                    self.detail_close_attempts = 0
                    return self.double_click_item(center, f'{group.removesuffix("价值")}第 {index + 1} 格')
            offset += len(centers)
        return self.transfer_fail('未找到可卸下的物品')
