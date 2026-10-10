"""独立关闭贝果搜查面板，不执行收集或交互。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_node import operation_node
from zzz_od.application.bagel.bagel_const import CONTAINER_TITLE_AREAS
from zzz_od.application.bagel.bagel_operation import BagelOperation

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelCloseSearch(BagelOperation):
    """等待搜索完成，关闭面板，并确认回到局内。"""

    def __init__(self, ctx: ZContext) -> None:
        """只处理已打开的搜查面板。"""
        super().__init__(ctx, op_name='贝果-关闭搜查面板', timeout_seconds=30)

    @operation_node(name='关闭搜查面板', is_start_node=True)
    def close_panel(self) -> OperationRoundResult:
        """搜索未结束时等待；点击返回后必须看到局内画面才完成。"""
        if self.is_bagel_result():
            return self.round_fail(self.STATUS_DEFEATED)
        has_title = any(
            self.round_by_find_area(self.last_screenshot, '贝果-局内', area).is_success
            for area in CONTAINER_TITLE_AREAS.values()
        )
        if not has_title:
            if self.round_by_find_area(
                self.last_screenshot, '战斗画面', '按键-普通攻击'
            ).is_success:
                return self.round_success('已关闭搜查面板')
            return self.round_wait('等待回到局内', wait=0.3)
        if not self.round_by_find_area(
            self.last_screenshot, '贝果-局内', '搜查完成'
        ).is_success:
            return self.round_wait('等待搜查完成再关闭', wait=0.3)
        self.round_by_click_area('贝果-局内', '搜查返回')
        return self.round_wait('等待搜查面板关闭', wait=0.8)
