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
from zzz_od.application.bagel.bagel_store_carried import BagelStoreCarried

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_base import OperationResult
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelSettleWarehouse(BagelOperation):
    """有物入仓后按开关清理；空箱跳过出售，所有结算都核对安全箱和容量。"""

    STATUS_DONE: str = BagelDeposit.STATUS_DONE

    def __init__(
        self, ctx: ZContext, auto_clean: bool, filter_areas: tuple[str, ...] = FILTER_TICKS,
        *, sell_due: bool = True, starting: bool = False,
    ) -> None:
        """应用决定本次是否到期；满仓或残留允许提前出售一次。"""
        super().__init__(ctx, op_name='贝果-结算仓库', timeout_seconds=180)
        self.starting: bool = starting
        self.auto_clean: bool = auto_clean
        self.filter_areas: tuple[str, ...] = filter_areas
        self.sell_due: bool = sell_due
        self.deposit_status: str = BagelDeposit.STATUS_EMPTY
        self.sale_completed: bool = False
        self.retry_deposit: bool = False

    def handle_init(self) -> None:
        """同一操作再次运行也不能沿用上次出售结果。"""
        super().handle_init()
        self.deposit_status = BagelDeposit.STATUS_EMPTY
        self.sale_completed = False
        self.retry_deposit = False

    def _deposit(self, retry: bool = False) -> OperationResult:
        """启动核对全部携带物，正常结算核对安全箱；共用出售和重试次数限制。"""
        if self.starting:
            result = BagelStoreCarried(self.ctx, return_on_remaining=True, click_when_empty=retry).execute()
            if result.success and result.status != BagelDeposit.STATUS_FULL:
                result.status = BagelDeposit.STATUS_DONE if result.data.get('moved', 0) else BagelDeposit.STATUS_EMPTY
            return result
        return BagelDeposit(self.ctx, return_on_remaining=True, click_when_empty=retry).execute()

    def _warehouse_ready(self) -> bool:
        """启动可在备战仓库；正式结算必须在退出后的仓库。"""
        names = ('放入仓库', '批量出售' if self.starting else '返回研究站')
        return all(self.round_by_find_area(self.last_screenshot, '贝果-仓库', name).is_success for name in names)

    @operation_node(name='首次入仓', is_start_node=True, screenshot_before_round=False)
    def deposit_first(self) -> OperationRoundResult:
        """先尝试一次入仓；明确的残留交给出售后一次重试。"""
        result = self._deposit()
        if not result.success:
            return self.round_by_op_result(result)
        if result.status == BagelDeposit.STATUS_FULL:
            if not self.auto_clean:
                return self.round_fail('安全箱仍有物资且自动清理关闭，停止并保留现场')
            self.retry_deposit = True
        self.deposit_status = result.status
        return self.round_success('已入仓')

    @node_from(from_name='首次入仓', status='已入仓')
    @operation_node(name='入仓后清理', timeout_seconds=100)
    def clean_after_deposit(self) -> OperationRoundResult:
        """空箱或清理关闭时只跳过出售，继续执行末尾核验。"""
        if self.deposit_status == BagelDeposit.STATUS_EMPTY:
            log.info('贝果空箱结算：跳过出售，继续核对安全箱和仓库容量')
            return self.round_success(self.deposit_status)
        if not self.auto_clean:
            return self.round_success(self.deposit_status)
        if not self._warehouse_ready():
            return self.round_retry('等待入仓后的仓库画面', wait=0.5)
        occupied = safe_occupied_indices(self.last_screenshot)
        pair = bagel_screen.parse_capacity_pair(bagel_screen.read_area(
            self.ctx, self.last_screenshot, '贝果-仓库', '仓库数量',
        ))
        if occupied is None or pair is None:
            return self.round_fail('出售前安全箱或仓库容量不明，停止并保留现场')
        if occupied:
            self.retry_deposit = True
        if not self.sell_due and not self.retry_deposit and pair[0] < pair[1]:
            log.info('贝果结算：未到出售间隔，本局只入仓')
            return self.round_success(self.deposit_status)
        reason = '残留物资' if self.retry_deposit else '仓库已满' if pair[0] >= pair[1] else '到期或正常结束'
        log.info('贝果结算：%s，按所选方案出售一次', reason)
        result = BagelCleanWarehouse(
            self.ctx, self.filter_areas, allow_safe_items=self.retry_deposit,
        ).execute()
        if not result.success:
            return self.round_by_op_result(result)
        log.info('贝果仓库清理完成：%s', result.status)
        self.sale_completed = True
        return self.round_success(self.deposit_status)

    @node_from(from_name='入仓后清理')
    @operation_node(name='出售后重试入仓', screenshot_before_round=False)
    def deposit_after_sale(self) -> OperationRoundResult:
        """只给有残留的结算一次再入仓机会，不能再次出售。"""
        if not self.retry_deposit:
            return self.round_success(self.deposit_status)
        log.info('贝果结算：出售后重试一次入仓')
        result = self._deposit(retry=True)
        if not result.success:
            return self.round_by_op_result(result)
        if result.status == BagelDeposit.STATUS_FULL:
            return self.round_fail('出售后重试入仓仍有残留，视为爆仓，停止并保留现场')
        self.deposit_status = BagelDeposit.STATUS_DONE
        return self.round_success(self.deposit_status)

    @node_from(from_name='出售后重试入仓')
    @operation_node(name='核对结算后仓库', timeout_seconds=10)
    def verify_warehouse_capacity(self) -> OperationRoundResult:
        """用新画面确认安全箱为空且容量可读；仓库已满不阻止返回和开新局。"""
        if not self._warehouse_ready():
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
        log.info('贝果结算核验：安全箱已空，仓库 %s/%s，允许结束结算', pair[0], pair[1])
        return self.round_success(self.deposit_status, data={'sale_completed': self.sale_completed})
