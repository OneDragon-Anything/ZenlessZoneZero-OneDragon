from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel import bagel_screen
from zzz_od.application.bagel.bagel_clean import FILTER_TICKS, BagelCleanWarehouse
from zzz_od.application.bagel.bagel_deposit import BagelDeposit
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_slots import safe_occupied_indices

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelSettleWarehouse(BagelOperation):
    """入仓后按开关清理；仓满且安全箱有物时保留现场。"""

    STATUS_DONE: str = BagelDeposit.STATUS_DONE
    # 空箱本局零收获。独立终态：不进入出售，也不做仓满核验，直接结束。
    STATUS_SKIPPED_EMPTY: str = '空箱局，未做任何出售'

    def __init__(
        self, ctx: ZContext, auto_clean: bool, filter_areas: tuple[str, ...] = FILTER_TICKS,
    ) -> None:
        """auto_clean 为假时只入仓，仓满直接失败。"""
        super().__init__(ctx, op_name='贝果-结算仓库', timeout_seconds=180)
        self.auto_clean: bool = auto_clean
        self.filter_areas: tuple[str, ...] = filter_areas
        self.deposit_status: str = BagelDeposit.STATUS_EMPTY

    @operation_node(name='首次入仓', is_start_node=True, screenshot_before_round=False)
    def deposit_first(self) -> OperationRoundResult:
        """先尝试入仓；满了且仍有物资则停止；空箱不做任何出售操作。"""
        result = BagelDeposit(self.ctx).execute()
        if not result.success:
            return self.round_by_op_result(result)
        if result.status == BagelDeposit.STATUS_FULL:
            return self.round_fail('仓库已满且安全箱仍有物资，禁止批量出售，停止并保留现场')
        self.deposit_status = result.status
        if result.status == BagelDeposit.STATUS_EMPTY:
            # 本局零收获。空箱不该去点仓库的批量出售：没有东西可卖，白跑一趟，
            # 万一筛选点错反而会卖掉仓库里的存货。
            return self.round_success(self.STATUS_SKIPPED_EMPTY)
        return self.round_success('已入仓')

    @node_from(from_name='首次入仓', status='已入仓')
    @operation_node(name='入仓后清理', screenshot_before_round=False)
    def clean_after_deposit(self) -> OperationRoundResult:
        """开关关闭则跳过出售。"""
        if not self.auto_clean:
            return self.round_success(self.deposit_status)
        result = BagelCleanWarehouse(self.ctx, self.filter_areas).execute()
        if not result.success:
            return self.round_by_op_result(result)
        log.info('贝果仓库清理完成：%s', result.status)
        return self.round_success(self.deposit_status)

    @node_from(from_name='入仓后清理')
    @operation_node(name='核对结算后仓库', timeout_seconds=10)
    def verify_warehouse_capacity(self) -> OperationRoundResult:
        """用处理结束后的新画面确认安全箱为空且仓库未满，再允许返回并开新局。"""
        if not all(self.round_by_find_area(
            self.last_screenshot, '贝果-仓库', area,
        ).is_success for area in ('放入仓库', '返回研究站')):
            return self.round_retry('等待结算后仓库画面', wait=0.5)
        occupied = safe_occupied_indices(self.last_screenshot)
        if occupied is None:
            return self.round_fail('结算后安全箱格子状态不明，停止并保留现场')
        if occupied:
            return self.round_fail('结算后安全箱仍有物资，停止并保留现场')
        pair = bagel_screen.parse_capacity_pair(bagel_screen.read_area(
            self.ctx, self.last_screenshot, '贝果-仓库', '仓库数量',
        ))
        if pair is None:
            return self.round_retry('结算后无法核对仓库容量，停止前再看一帧', wait=0.5)
        if pair[0] >= pair[1]:
            return self.round_fail(f'结算后仓库已满（{pair[0]}/{pair[1]}），停止并保留现场')
        return self.round_success(self.deposit_status)
