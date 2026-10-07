from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.application.bagel.bagel_screen import parse_capacity_pair, read_area
from zzz_od.application.bagel.bagel_slots import safe_occupied_indices

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelDeposit(BagelOperation):
    """结算仓库中点击放入仓库，并核对安全箱清空与仓库数量变化。"""

    STATUS_EMPTY: str = '安全箱已空'
    STATUS_DONE: str = '已入仓并清空安全箱'
    STATUS_FULL: str = '仓库已满'

    def __init__(self, ctx: ZContext) -> None:
        """退出到仓库后调用；不能只凭点击成功记账。"""
        super().__init__(ctx, op_name='贝果-放入仓库', timeout_seconds=45)
        self.safe_before: int = 0
        self.warehouse_before: int | None = None
        self._full_waits: int = 0

    def handle_init(self) -> None:
        """清空入仓前基线。"""
        super().handle_init()
        self.safe_before = 0
        self.warehouse_before = None
        self._full_waits = 0

    def _warehouse_ready(self) -> bool:
        """必须同时看到放入仓库与返回研究站。"""
        return all(
            self.round_by_find_area(self.last_screenshot, '贝果-仓库', area).is_success
            for area in ('放入仓库', '返回研究站')
        )

    def _safe_count(self) -> int | None:
        """统计已开放格内的物品；未知不能当空箱。"""
        occupied = safe_occupied_indices(self.last_screenshot)
        return None if occupied is None else len(occupied)

    def _warehouse_pair(self) -> tuple[int, int] | None:
        """读取右侧全部占用与容量。"""
        text = read_area(self.ctx, self.last_screenshot, '贝果-仓库', '仓库数量')
        return parse_capacity_pair(text)

    def _warehouse_count(self) -> int | None:
        """读取右侧全部占用；识别失败返回 None。"""
        pair = self._warehouse_pair()
        return None if pair is None else pair[0]

    @operation_node(name='核对安全箱并入仓', is_start_node=True, timeout_seconds=20)
    def prepare_and_click(self) -> OperationRoundResult:
        """空箱直接成功结束；有物则记录基线后点击放入仓库。"""
        if not self._warehouse_ready():
            return self.round_retry('未到结算仓库', wait=1)
        safe_count = self._safe_count()
        if safe_count is None:
            return self.round_fail('安全箱格子状态不明，停止并保留现场')
        self.safe_before = safe_count
        self.warehouse_before = self._warehouse_count()
        if self.warehouse_before is None:
            return self.round_fail('无法读取仓库数量，停止并保留现场')
        if self.safe_before == 0:
            return self.round_success(self.STATUS_EMPTY, data={'moved': 0})
        log.info(
            '贝果入仓：安全箱 %s 格，仓库基线 %s',
            self.safe_before, self.warehouse_before,
        )
        return self.round_by_find_and_click_area(
            self.last_screenshot, '贝果-仓库', '放入仓库',
            success_wait=1.0, retry_wait=1,
        )

    @node_from(from_name='核对安全箱并入仓', status='放入仓库')
    @operation_node(name='确认安全箱清空', timeout_seconds=20)
    def confirm_cleared(self) -> OperationRoundResult:
        """点击入仓后安全箱必须清空；堆叠可不增仓库格数，但不能减少。"""
        if not self._warehouse_ready():
            self._full_waits = 0
            return self.round_wait('等待入仓后的仓库画面', wait=0.5)
        safe_after = self._safe_count()
        if safe_after is None:
            return self.round_fail('入仓后安全箱格子状态不明，停止并保留现场')
        if safe_after > 0:
            pair = self._warehouse_pair()
            # 仓满要先判：格数不够时部分入仓是预期行为，不是物资去向不明。
            if pair is not None and pair[0] >= pair[1]:
                self._full_waits += 1
                if self._full_waits >= 6:
                    log.info('贝果入仓：仓库 %s/%s 且安全箱仍占用，记为已满', pair[0], pair[1])
                    return self.round_success(self.STATUS_FULL, data={'safe_count': safe_after})
                return self.round_wait('仓库已满，等待确认', wait=0.5)
            if safe_after < self.safe_before:
                return self.round_fail(
                    f'仅部分入仓，安全箱 {self.safe_before} -> {safe_after} 格，'
                    '停止并保留现场核对物资去向',
                )
            self._full_waits = 0
            # 第一次点击可能没让游戏入仓。格子还在就再点，不要只重数。
            clicked = self.round_by_find_and_click_area(
                self.last_screenshot, '贝果-仓库', '放入仓库',
                success_wait=0.8, retry_wait=0.8,
            )
            if not clicked.is_success:
                return clicked
            return self.round_retry(
                f'安全箱仍有 {safe_after} 格占用，等待清空或停止', wait=0.2,
            )
        self._full_waits = 0
        warehouse_after = self._warehouse_count()
        if warehouse_after is None:
            return self.round_fail('入仓后无法读取仓库数量')
        # 全部(N/M) 是占用格数，不是物品总数；并入已有堆叠时 N 可以不变。
        if self.warehouse_before is None or warehouse_after < self.warehouse_before:
            return self.round_fail(
                f'仓库占用异常（{self.warehouse_before} -> {warehouse_after}），不能记为入仓成功',
            )
        if self.warehouse_before == warehouse_after:
            pair = self._warehouse_pair()
            if pair is None:
                return self.round_fail('入仓后无法核对仓库容量，停止并保留现场')
            if pair[0] >= pair[1]:
                return self.round_fail('满仓后安全箱清空但仓库占用未变，不能证明物资已入仓')
        log.info(
            '贝果入仓确认：安全箱已空，仓库 %s -> %s',
            self.warehouse_before, warehouse_after,
        )
        return self.round_success(
            self.STATUS_DONE,
            data={
                'moved': self.safe_before,
                'warehouse_before': self.warehouse_before,
                'warehouse_after': warehouse_after,
            },
        )
