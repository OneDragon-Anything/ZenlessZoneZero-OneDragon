from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_screen import (
    parse_capacity_pair,
    read_area,
    warehouse_sale_state,
)
from zzz_od.application.bagel.bagel_slots import (
    WAREHOUSE_SAFE_CENTERS,
    inspect_safe_slots,
)
from zzz_od.application.bagel.bagel_transfer import BagelTransferOperation

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


def read_carried_backpack(ctx: ZContext, screen: MatLike) -> tuple[int, int] | None:
    """读取普通背包占用数和容量；固定区域失效时按唯一标题定位数字。"""
    pair = parse_capacity_pair(read_area(ctx, screen, '贝果-仓库', '背包数量'))
    if pair is not None:
        return pair
    matches = ctx.ocr_service.get_ocr_result_list(screen)
    candidates: list[tuple[int, int]] = []
    for label in matches:
        if '背包' not in label.data or not (180 < label.center.x < 850 and 90 < label.center.y < 780):
            continue
        row = sorted((match for match in matches
                      if 180 < match.center.x < 850 and abs(match.center.y - label.center.y) <= 12),
                     key=lambda match: match.x)
        text = ''.join(match.data for match in row)
        if len(re.findall(r'[0-9]+\s*/\s*[0-9]+', text)) != 1:
            continue
        pair = parse_capacity_pair(text)
        if pair is not None:
            candidates.append(pair)
    return candidates[0] if len(candidates) == 1 else None


class BagelStoreCarried(BagelTransferOperation):
    """通过仓库左下批量按钮转存携带物，两个容器清空后仍停在仓库。"""

    def __init__(
        self, ctx: ZContext, *, return_on_remaining: bool = False, click_when_empty: bool = False,
    ) -> None:
        """同时支持备战仓库与结算仓库，只点一次放入仓库。"""
        super().__init__(ctx, op_name='贝果-批量转存携带物')
        self.return_on_remaining: bool = return_on_remaining
        self.click_when_empty: bool = click_when_empty
        self.before_counts: tuple[int, int, int, int, int] | None = None

    def handle_init(self) -> None:
        """清除上一轮转存的数量基线。"""
        super().handle_init()
        self.before_counts = None

    @operation_node(name='批量转存携带物', is_start_node=True)
    def store_next(self) -> OperationRoundResult:
        """核对携带物后批量入仓；输入只发送一次，回读两个容器都清空才完成。"""
        sale_state = warehouse_sale_state(self.ctx, self.last_screenshot)
        if sale_state is not None:
            self._stable_image = None
            return self.transfer_fail(f'检测到仓库出售状态（{sale_state}），停止并保留现场')
        if not self.round_by_find_area(self.last_screenshot, '贝果-仓库', '放入仓库').is_success:
            self._stable_image = None
            return self.read_again('未识别仓库主画面')
        backpack = read_carried_backpack(self.ctx, self.last_screenshot)
        warehouse = parse_capacity_pair(read_area(self.ctx, self.last_screenshot, '贝果-仓库', '仓库数量'))
        safe = inspect_safe_slots(self.last_screenshot, WAREHOUSE_SAFE_CENTERS)
        if backpack is None or warehouse is None or safe is None:
            self._stable_image = None
            return self.read_again('无法完整识别背包、安全箱或仓库数量')
        safe_count = len(safe.occupied)
        self.observation = f'背包 {backpack[0]}/{backpack[1]}，安全箱 {safe_count} 格，仓库 {warehouse[0]}/{warehouse[1]}'
        counts = (backpack[0], safe_count, warehouse[0], backpack[1], warehouse[1])
        # 普通背包只核验数字；安全箱没有占用数字，仍按格子状态核验。
        signature = (*counts, safe)
        if not self.stable_slots((), signature):
            if self.pending:
                return self.wait_transfer('等待转存后读数稳定')
            return self.read_again('等待仓库读数稳定')
        if self.pending:
            self.read_misses = 0
            return self.confirm_transfer(counts)
        if backpack[0] == 0 and safe_count == 0 and not self.click_when_empty:
            return self.round_success('携带物已全部转存', data={'moved': self.moved, 'warehouse': warehouse})
        if warehouse[0] >= warehouse[1] and not self.return_on_remaining:
            return self.transfer_fail(f'仓库已满 {warehouse[0]}/{warehouse[1]}')
        if not self.ctx.run_context.is_context_running:
            return self.round_wait('等待恢复后重新核对仓库', wait=0.5)
        self.before_counts = counts
        self.source_label = '背包和安全箱批量入仓'
        self.read_misses = 0
        self.pending = True
        self.pending_checks = 0
        self.pending_started = time.monotonic()
        self._stable_image = None
        log.info('贝果携带物入仓：%s；有残留时返回结算=%s，空包仍点击=%s',
                 self.observation, self.return_on_remaining, self.click_when_empty)
        result = self.round_by_click_area('贝果-仓库', '放入仓库')
        if not result.is_success:
            return self.transfer_fail('点击放入仓库失败')
        return self.round_wait('等待批量入仓结果', wait=0.5)

    def confirm_transfer(self, counts: tuple[int, int, int, int, int]) -> OperationRoundResult:
        """两个容器全部清空才完成；允许堆叠，部分转存停止且不补点。"""
        before = self.before_counts
        if before is None:
            return self.transfer_fail('缺少转存前数量')
        if counts[3:] != before[3:] or counts[2] < before[2]:
            return self.transfer_fail(f'转存前后容量或仓库占用异常 {before} -> {counts}')
        if counts[:2] == (0, 0):
            self.moved += before[0] + before[1]
            self.pending = False
            log.info('贝果携带物入仓确认：背包=%s -> 0，安全箱=%s -> 0，仓库=%s -> %s/%s',
                     before[0], before[1], before[2], counts[2], counts[4])
            return self.round_success('携带物已全部转存', data={'moved': self.moved, 'warehouse': (counts[2], counts[4])})
        # 仓库有空位且携带数量未变，只能说明结果尚未确认，不能提前交给出售。
        if counts[:2] == before[:2] and counts[2] < counts[4]:
            return self.wait_transfer('入仓操作后物品未完整转出，等待核对')
        if self.return_on_remaining and counts[0] <= before[0] and counts[1] <= before[1]:
            self.pending = False
            return self.round_success('仓库已满', data={'safe_count': counts[1], 'backpack_count': counts[0]})
        if counts[0] <= before[0] and counts[1] <= before[1] and counts[:2] != before[:2]:
            self.moved += before[0] + before[1] - counts[0] - counts[1]
            return self.transfer_fail(f'仅部分入仓 {before[:2]} -> {counts[:2]}，停止核对剩余物资')
        if counts[:2] != before[:2]:
            return self.transfer_fail(f'携带物数量变化异常 {before[:2]} -> {counts[:2]}')
        return self.wait_transfer('入仓操作后物品未完整转出，等待核对')
