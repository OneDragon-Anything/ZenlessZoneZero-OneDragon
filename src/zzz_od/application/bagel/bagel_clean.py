from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_const import (
    DEFAULT_CLEAN_QUALITIES,
    DEFAULT_CLEAN_TYPES,
)
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_screen import (
    parse_capacity_pair,
    parse_filter_count,
    read_area,
)
from zzz_od.application.bagel.bagel_slots import safe_occupied_indices

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext

FILTER_TICKS: tuple[str, ...] = tuple(
    f'筛选-{name}' for name in (*DEFAULT_CLEAN_TYPES, *DEFAULT_CLEAN_QUALITIES)
)
FILTER_EXCLUDED: tuple[str, ...] = (
    '筛选-全部', '筛选-Z', '筛选-装备', '筛选-战术道具', '筛选-门禁卡',
)
# 选中底色覆盖大片按钮；未选中的彩色图标（门禁卡实测约 0.025）不能当成过渡态。
_FILTER_SELECTED_MIN: float = 0.2
_FILTER_UNSELECTED_MAX: float = 0.08


class BagelCleanWarehouse(BagelOperation):
    """用仓库快速选择卖掉贵重物品、战术棱镜、其他的 C–S，只留 Z。

    常规模式要求安全箱为空才允许进入批量出售。仓满时安全箱必然有物（那正是放不进去
    的部分），此时用 `force_make_room=True` 强制腾位：安全箱占用格作为基线记录下来，
    出售后要求它一字不差，而不是要求清空。快速选择只作用于右侧仓库格，安全箱不在
    出售范围内，所以仓满是唯一能腾位的场景。
    """

    STATUS_SKIPPED: str = '没有可出售物品'
    STATUS_DONE: str = '已批量出售'

    def __init__(
        self, ctx: ZContext, filter_areas: tuple[str, ...] = FILTER_TICKS,
        force_make_room: bool = False,
    ) -> None:
        """入仓后调用；不点整理，不点自动转化货币。"""
        super().__init__(ctx, op_name='贝果-仓库清理', timeout_seconds=90)
        all_areas = (*FILTER_EXCLUDED, *FILTER_TICKS)
        if len(set(filter_areas)) != len(filter_areas) or any(name not in all_areas or name == '筛选-全部' for name in filter_areas):
            raise ValueError('清理筛选包含重复或未知区域')
        self.filter_areas: frozenset[str] = frozenset(filter_areas)
        self.force_make_room: bool = force_make_room
        self._filter_count: int | None = None
        self._safe_baseline: tuple[int, ...] | None = None
        self._warehouse_before: int | None = None

    def handle_init(self) -> None:
        """每次执行清空勾选进度。"""
        super().handle_init()
        self._filter_count = None
        self._safe_baseline = None
        self._warehouse_before = None

    def _has_area(self, area_name: str) -> bool:
        """当前帧是否命中仓库指定文字区。"""
        return self.round_by_find_area(
            self.last_screenshot, '贝果-仓库', area_name,
        ).is_success

    def _warehouse_idle(self) -> bool:
        """仓库主界面；研究站打开仓库时没有结算页的返回研究站按钮。"""
        return all(self._has_area(name) for name in ('放入仓库', '批量出售'))

    def _safe_occupied(self) -> tuple[int, ...] | None:
        """仅在仓库主界面读安全箱占用；出售弹窗会遮挡格子。非主界面返回 None。"""
        if not self._warehouse_idle():
            return None
        return safe_occupied_indices(self.last_screenshot)

    def _check_safe_before_sell(self) -> tuple[int, ...] | None:
        """出售前记录安全箱基线；不允许出售时返回 None。

        常规模式要求空箱；仓满强制腾位时安全箱必然有物，那正是入仓放不进去的部分，
        如实记下占用格作为基线，出售后用来核对「一件都没动」。
        """
        occupied = self._safe_occupied()
        if occupied is None:
            return None
        if occupied and not self.force_make_room:
            return None
        return occupied

    def _warehouse_count(self) -> int | None:
        """读取仓库占用；文字不清晰时不能验证腾位。"""
        pair = parse_capacity_pair(read_area(self.ctx, self.last_screenshot, '贝果-仓库', '仓库数量'))
        return None if pair is None else pair[0]

    def _in_filter(self) -> bool:
        """快速选择弹窗是否打开。"""
        return self._has_area('快速选择标题')

    def _in_sell_mode(self) -> bool:
        """已点批量出售，底栏为取消/批量选择/确认出售。"""
        return self._has_area('取消出售') and self._has_area('批量选择')

    def _filter_states(self) -> dict[str, bool] | None:
        """读取全部筛选按钮的蓝底选中态；过渡色或区域缺失时不作判断。"""
        states: dict[str, bool] = {}
        for name in (*FILTER_EXCLUDED, *FILTER_TICKS):
            area = self.ctx.screen_loader.get_area('贝果-仓库', name)
            if area is None:
                return None
            rect = area.pc_rect
            crop = self.last_screenshot[rect.y1:rect.y2, rect.x1:rect.x2]
            if crop.size == 0 or crop.ndim != 3:
                return None
            # 原生实拍：选中底色 RGB 约 (0, 145, 255)，未选中为深灰。
            blue = (crop[:, :, 0] < 80) & (crop[:, :, 1] > 80) & (crop[:, :, 2] > 180)
            ratio = float(np.mean(blue))
            if ratio >= _FILTER_SELECTED_MIN:
                states[name] = True
            elif ratio <= _FILTER_UNSELECTED_MAX:
                states[name] = False
            else:
                return None
        return states

    @operation_node(name='打开批量出售', is_start_node=True, node_max_retry_times=8)
    def open_sell(self) -> OperationRoundResult:
        """进入出售态；已在弹窗或出售底栏则跳过。"""
        if self._warehouse_idle():
            baseline = self._check_safe_before_sell()
            if baseline is None:
                if safe_occupied_indices(self.last_screenshot) is None:
                    return self.round_fail('安全箱格子状态不明，不能批量出售，停止并保留现场')
                return self.round_fail('安全箱仍有物资，不能批量出售，停止并保留现场')
            self._safe_baseline = baseline
            self._warehouse_before = self._warehouse_count()
            if self._warehouse_before is None:
                return self.round_fail('出售前无法读取仓库占用，停止并保留现场')
        elif self._safe_baseline is None:
            return self.round_fail('出售前未确认安全箱状态，停止并保留现场')
        if self._in_filter():
            return self.round_success('已到快速选择')
        if self._in_sell_mode():
            return self.round_success('已到批量出售')
        if not self._has_area('批量出售'):
            return self.round_retry('未识别仓库出售入口', wait=0.6)
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-仓库', '批量出售',
            success_wait=0.8, retry_wait=0.6,
        )

    @node_from(from_name='打开批量出售', status='批量出售')
    @node_from(from_name='打开批量出售', status='已到批量出售')
    @operation_node(name='打开快速选择', node_max_retry_times=8)
    def open_filter(self) -> OperationRoundResult:
        """打开快速选择；已打开则往下勾选。"""
        if self._in_filter():
            return self.round_success('已到快速选择')
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-仓库', '批量选择',
            success_wait=0.8, retry_wait=0.6,
        )

    @node_from(from_name='打开批量出售', status='已到快速选择')
    @node_from(from_name='打开快速选择')
    @operation_node(name='勾选筛选', node_max_retry_times=8, timeout_seconds=25)
    def tick_filter(self) -> OperationRoundResult:
        """先取消禁止项，再补选目标项；每次点击后回读，不盲目翻转已有选择。"""
        if not self._in_filter():
            return self.round_fail('快速选择已关闭，停止并保留现场')
        states = self._filter_states()
        if states is None:
            return self.round_retry('筛选状态不清晰', wait=0.5)
        for name, selected in states.items():
            if selected == (name in self.filter_areas):
                continue
            result = self.round_by_find_and_click_area(
                self.last_screenshot, '贝果-仓库', name,
                success_wait=0.5, retry_wait=0.5,
            )
            if result.is_success:
                # 留在本节点等待下一帧核对；点击无效时不会推进到出售。
                return self.round_wait('等待筛选状态更新', wait=0.5)
            return result
        return self.round_success('勾选完成')

    @node_from(from_name='勾选筛选', status='勾选完成')
    @operation_node(name='读取筛选数量')
    def read_count(self) -> OperationRoundResult:
        """用弹窗里的件数决定要不要点确认出售。"""
        if not self._in_filter():
            return self.round_fail('读取筛选数量时快速选择已关闭')
        states = self._filter_states()
        if states is None or any(selected != (name in self.filter_areas) for name, selected in states.items()):
            return self.round_fail('筛选条件不符，停止并保留现场')
        text = read_area(self.ctx, self.last_screenshot, '贝果-仓库', '筛选数量')
        count = parse_filter_count(text)
        if count is None:
            return self.round_fail(f'无法读取筛选数量（{text}），停止并保留现场')
        self._filter_count = count
        log.info('贝果仓库清理：筛选命中 %s 件', count)
        if count <= 0:
            return self.round_success('无需出售')
        return self.round_success('有待出售')

    @node_from(from_name='读取筛选数量')
    @operation_node(name='确认筛选', node_max_retry_times=8)
    def confirm_filter(self) -> OperationRoundResult:
        """点确认后必须看到快速选择关掉，才去决定是否出售。"""
        if not self._in_filter():
            return self.round_success('筛选确认')
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-仓库', '筛选确认',
            until_not_find_all=[('贝果-仓库', '快速选择标题')],
            success_wait=0.8, retry_wait=0.6,
        )

    @node_from(from_name='确认筛选', status='筛选确认')
    @operation_node(name='决定是否出售')
    def decide_sell(self) -> OperationRoundResult:
        """0 件则取消出售态；有件才点确认出售。"""
        if self._filter_count is None:
            return self.round_fail('缺少筛选数量')
        if self._filter_count <= 0:
            return self.round_success('跳过出售')
        return self.round_success('去确认出售')

    @node_from(from_name='决定是否出售', status='去确认出售')
    @operation_node(name='点击确认出售', node_max_retry_times=8)
    def click_sell(self) -> OperationRoundResult:
        """卖掉当前选中项。快速选择还开着时，底栏确认出售被挡住，不去找它。"""
        if self._in_filter():
            return self.round_retry('快速选择未关闭', wait=0.5)
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-仓库', '确认出售',
            until_find_all=[('贝果-仓库', '出售确认标题')],
            success_wait=1.0, retry_wait=0.6,
        )

    @node_from(from_name='点击确认出售', status='确认出售')
    @operation_node(name='确认出售弹窗', timeout_seconds=15)
    def confirm_sale_dialog(self) -> OperationRoundResult:
        """只确认本次已核对筛选、有件数的出售预览。"""
        if self._filter_count is None or self._filter_count <= 0:
            return self.round_fail('缺少已核对的待出售件数')
        if self._safe_baseline is None:
            return self.round_fail('出售前未确认安全箱状态，停止并保留现场')
        if self._warehouse_before is None:
            return self.round_fail('出售前未记录仓库占用，停止并保留现场')
        if not self._has_area('出售确认标题'):
            return self.round_wait('等待出售确认弹窗', wait=0.5)
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-仓库', '出售弹窗确认',
            success_wait=1.0, retry_wait=0.5,
        )

    @node_from(from_name='确认出售弹窗', status='出售弹窗确认')
    @operation_node(name='等待回到仓库', timeout_seconds=20)
    def wait_idle_after_sell(self) -> OperationRoundResult:
        """关闭出售获得硬币提示，再核对回到仓库主界面。"""
        if self._warehouse_idle():
            # 安全箱不在出售范围内，出售后必须与出售前基线一字不差：
            # 常规模式基线是空箱，强制腾位模式基线是入仓前那几格。
            after_safe = self._safe_occupied()
            if after_safe is None:
                return self.round_fail('出售后安全箱格子状态不明，停止并保留现场')
            if after_safe != self._safe_baseline:
                return self.round_fail(
                    f'出售后安全箱与出售前不一致（{self._safe_baseline} -> {after_safe}），停止并保留现场',
                )
            warehouse_after = self._warehouse_count()
            if warehouse_after is None or self._warehouse_before is None:
                return self.round_fail('出售后无法核对仓库占用，停止并保留现场')
            if warehouse_after >= self._warehouse_before:
                return self.round_fail(
                    f'出售后仓库未腾位（{self._warehouse_before} -> {warehouse_after}），停止并保留现场',
                )
            return self.round_success(self.STATUS_DONE)
        if self._has_area('出售获得标题') and self._has_area('出售获得货币'):
            result = self.round_by_find_and_click_area(
                self.last_screenshot, '贝果-仓库', '出售获得确认',
                success_wait=0.8, retry_wait=0.5,
            )
            if result.is_success:
                return self.round_wait('等待关闭出售获得提示', wait=0.5)
            return result
        if self._in_sell_mode():
            return self.round_wait('等待出售完成', wait=0.5)
        return self.round_wait('等待回到仓库主界面', wait=0.5)

    @node_from(from_name='决定是否出售', status='跳过出售')
    @operation_node(name='取消出售', node_max_retry_times=8)
    def cancel_sell(self) -> OperationRoundResult:
        """没有可卖项时退出出售态。"""
        if self._warehouse_idle():
            return self.round_success(self.STATUS_SKIPPED)
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-仓库', '取消出售',
            success_wait=0.8, retry_wait=0.6,
        )

    @node_from(from_name='取消出售', status='取消出售')
    @operation_node(name='确认已取消', timeout_seconds=10)
    def confirm_cancelled(self) -> OperationRoundResult:
        """取消后应重新看到批量出售。"""
        if self._warehouse_idle():
            return self.round_success(self.STATUS_SKIPPED)
        return self.round_wait('等待退出出售', wait=0.5)
