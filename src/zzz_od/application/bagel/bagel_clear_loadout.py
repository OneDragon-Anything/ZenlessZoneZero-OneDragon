from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_screen import (
    complete_loadout,
    parse_capacity_pair,
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


class BagelClearLoadout(BagelTransferOperation):
    """从备战清空内容物及已装备物品，成功时仍停在零携带备战。"""

    def __init__(self, ctx: ZContext) -> None:
        """先清容器再卸装备，保留队伍，不调用结算出售。"""
        super().__init__(ctx, op_name='贝果-清空启动战备')
        self.required_slots: int = 0
        self.viewing_backpack: bool = False
        self.pending_center: Point | None = None
        self.pending_group: str = ''
        self.before_values: dict[str, str] = {}
        self.before_states: tuple[bool, ...] = ()
        self.unload_retries: int = 0
        self.unload_generation: int = 0

    def handle_init(self) -> None:
        """清除上次卸装的基线。"""
        super().handle_init()
        self.required_slots = 0
        self.viewing_backpack = False
        self.pending_center = None
        self.pending_group = ''
        self.before_values = {}
        self.before_states = ()
        self.unload_retries = 0
        self.unload_generation = 0

    def at_prepare(self) -> bool:
        """同时核对两个备战按钮，防止在仓储库存区使用装备槽坐标。"""
        return all(self.round_by_find_area(self.last_screenshot, '贝果-备战', name).is_success
                   for name in ('预设组合', '前往空洞'))

    @operation_node(name='核对启动携带', is_start_node=True)
    def inspect_loadout(self) -> OperationRoundResult:
        """识别完整五项及装备槽，决定是否需要清空。"""
        if not self.at_prepare():
            self._stable_image = None
            return self.read_again('未识别备战主画面')
        values = read_loadout(self.ctx, self.last_screenshot)
        self.observation = f'五项携带 {values}'
        if not complete_loadout(values):
            self._stable_image = None
            return self.read_again(f'五项携带识别不完整 {values}')
        if zero_loadout(values):
            return self.round_success('已是零携带')
        states = [carried_slot_state(self.last_screenshot, center) for center in LOADOUT_CENTERS]
        if None in states:
            self._stable_image = None
            return self.read_again('无法完整识别已装备槽位')
        # 空槽图案和物品图标会持续闪动；按完整读数及各槽占用状态判断稳定。
        if not self.stable_slots((), (*values.values(), *states)):
            return self.read_again('等待备战格子稳定')
        self.required_slots = sum(state is True for state in states)
        self.read_misses = 0
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
        """逐格快速双击入仓，确认原槽变空后才处理下一格。"""
        if not self.at_prepare():
            self._stable_image = None
            return self.read_again('未识别卸装后的备战')
        values = read_loadout(self.ctx, self.last_screenshot)
        self.observation = f'五项携带 {values}'
        if not complete_loadout(values):
            self._stable_image = None
            return self.read_again(f'无法完整核对卸装结果 {values}')
        if any(parse_capacity_pair(values[name])[0] != 0 for name in ('背包数量', '安全箱数量')):
            return self.transfer_fail(f'卸装时背包或安全箱出现物资 {values}')
        states = [carried_slot_state(self.last_screenshot, center) for center in LOADOUT_CENTERS]
        if None in states:
            self._stable_image = None
            return self.read_again('卸装槽位状态不清')
        # 不等待图标像素静止；源槽清空与价值变化仍由下面的独立判据核对。
        if not self.stable_slots((), (*values.values(), *states)):
            if self.pending:
                return self.wait_transfer('等待卸装结果稳定')
            return self.read_again('等待备战格子稳定')
        self.read_misses = 0
        if self.pending:
            if self.pending_center is None:
                return self.transfer_fail('缺少待核验槽位')
            if carried_slot_state(self.last_screenshot, self.pending_center) is not False:
                result = self.wait_transfer('双击后原装备槽仍有物品')
                if (result.is_fail and self.unload_retries == 0
                        and self.unload_generation == self.pause_generation
                        and values == self.before_values and tuple(states) == self.before_states):
                    self.unload_retries += 1
                    return self.double_click_item(self.pending_center, f'{self.source_label}（重试 1/1）')
                return result
            for group, _ in LOADOUT_GROUPS:
                before, after = int(self.before_values[group]), int(values[group])
                if (group == self.pending_group and after >= before) or (group != self.pending_group and after != before):
                    return self.transfer_fail(f'卸装价值变化异常 {self.before_values} -> {values}')
            self.finish_transfer()
            # 当前两帧已同时核对所有槽位与读数，可直接选择下一格或报告全空。
        if not any(states):
            if not zero_loadout(values):
                return self.transfer_fail(f'槽位已空但五项未归零 {values}')
            return self.round_success('战备已全部清空', data={'moved': self.moved})
        offset = 0
        for group, centers in LOADOUT_GROUPS:
            for index, center in enumerate(centers):
                if states[offset + index]:
                    if int(values[group]) == 0:
                        return self.transfer_fail(f'{group}为零但槽位仍有物品')
                    self.pending_center = center
                    self.pending_group = group
                    self.before_values = values
                    self.before_states = tuple(states)
                    self.unload_retries = 0
                    self.unload_generation = self.pause_generation
                    return self.double_click_item(center, f'{group.removesuffix("价值")}第 {index + 1} 格')
            offset += len(centers)
        return self.transfer_fail('未找到可卸下的物品')
