from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

import cv2

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_screen import (
    parse_capacity_pair,
    read_area,
    warehouse_sale_state,
)
from zzz_od.application.bagel.bagel_slots import (
    WAREHOUSE_SAFE_CENTERS,
    inspect_safe_slots,
)
from zzz_od.application.bagel.bagel_transfer import (
    BagelTransferOperation,
    carried_slot_state,
)

if TYPE_CHECKING:
    from cv2.typing import MatLike

    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


# 1080p 仓库布局来自清空战备录像；行位置由边框重新定位，兼容滚动后的偏移。
_BACKPACK_XS: tuple[int, ...] = (267, 371, 475, 579, 683, 787)


def read_carried_backpack(ctx: ZContext, screen: MatLike) -> tuple[tuple[int, int], int] | None:
    """读取背包数量与标题底部；结算奖励会把背包标题向下推。"""
    pair = parse_capacity_pair(read_area(ctx, screen, '贝果-仓库', '背包数量'))
    if pair is not None:
        area = ctx.screen_loader.get_area('贝果-仓库', '背包数量')
        return pair, area.pc_rect.y2
    matches = ctx.ocr_service.get_ocr_result_list(screen)
    candidates: list[tuple[tuple[int, int], int]] = []
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
            candidates.append((pair, max(match.y + match.h for match in row)))
    return candidates[0] if len(candidates) == 1 else None


def backpack_centers(screen: MatLike, header_bottom: int = 158) -> tuple[Point, ...]:
    """按仓库左侧格子边框找完整行，排除被裁断的首末行和库存区。"""
    gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
    contours, _ = cv2.findContours(cv2.Canny(gray, 40, 100), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    rows: dict[int, set[int]] = {}
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if not (x > 205 and x + width < 855 and y > max(160, header_bottom) and y + height < 780
                and 85 <= width <= 115 and 95 <= height <= 130):
            continue
        column = min(range(6), key=lambda index: abs(_BACKPACK_XS[index] - (x + width / 2)))
        if abs(_BACKPACK_XS[column] - (x + width / 2)) > 6:
            continue
        cy = round(y + height / 2)
        row = next((key for key in rows if abs(key - cy) <= 6), cy)
        rows.setdefault(row, set()).add(column)
    return tuple(
        Point(x, y) for y, columns in sorted(rows.items()) if len(columns) >= 4 for x in _BACKPACK_XS
    )


class BagelStoreCarried(BagelTransferOperation):
    """通过仓库左下批量按钮转存携带物，两个容器清空后仍停在仓库。"""

    def __init__(self, ctx: ZContext) -> None:
        """同时支持备战仓库与结算仓库，只点一次放入仓库。"""
        super().__init__(ctx, op_name='贝果-批量转存携带物')
        self.before_counts: tuple[int, int, int, int, int] | None = None

    def handle_init(self) -> None:
        """清除上一轮容器基线及滚动次数。"""
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
        backpack_info = read_carried_backpack(self.ctx, self.last_screenshot)
        warehouse = parse_capacity_pair(read_area(self.ctx, self.last_screenshot, '贝果-仓库', '仓库数量'))
        safe = inspect_safe_slots(self.last_screenshot, WAREHOUSE_SAFE_CENTERS)
        if backpack_info is None or warehouse is None or safe is None:
            self._stable_image = None
            return self.read_again('无法完整识别背包、安全箱或仓库数量')
        backpack, header_bottom = backpack_info
        safe_count = len(safe.occupied)
        self.observation = f'背包 {backpack[0]}/{backpack[1]}，安全箱 {safe_count} 格，仓库 {warehouse[0]}/{warehouse[1]}'
        counts = (backpack[0], safe_count, warehouse[0], backpack[1], warehouse[1])
        # 数量可能被误读为零，仍须核验可见格子，不能仅凭读数判定空包。
        centers = backpack_centers(self.last_screenshot, header_bottom)
        if not centers:
            self._stable_image = None
            return self.read_again('无法定位背包完整格子行')
        states = [carried_slot_state(self.last_screenshot, center) for center in centers]
        if None in states:
            self._stable_image = None
            return self.read_again('背包格子状态不清')
        if sum(state is True for state in states) > backpack[0]:
            self._stable_image = None
            return self.read_again('背包格子与占用数不符')
        # 图标会持续闪动；核对数量、行位置与每格占用，滚动或重排后重新等待。
        signature = (*counts, tuple(center.tuple() for center in centers), *states, safe)
        if not self.stable_slots((), signature):
            if self.pending:
                return self.wait_transfer('等待转存后格子稳定')
            return self.read_again('等待仓库格子稳定')
        if self.pending:
            self.read_misses = 0
            return self.confirm_transfer(counts)
        if backpack[0] == 0 and safe_count == 0:
            return self.round_success('携带物已全部转存', data={'moved': self.moved, 'warehouse': warehouse})
        if warehouse[0] >= warehouse[1]:
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
            return self.round_success('携带物已全部转存', data={'moved': self.moved, 'warehouse': (counts[2], counts[4])})
        if counts[0] <= before[0] and counts[1] <= before[1] and counts[:2] != before[:2]:
            self.moved += before[0] + before[1] - counts[0] - counts[1]
            return self.transfer_fail(f'仅部分入仓 {before[:2]} -> {counts[:2]}，停止核对剩余物资')
        if counts[:2] != before[:2]:
            return self.transfer_fail(f'携带物数量变化异常 {before[:2]} -> {counts[:2]}')
        return self.wait_transfer('入仓操作后物品未完整转出，等待核对')
