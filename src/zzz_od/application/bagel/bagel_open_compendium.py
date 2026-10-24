from __future__ import annotations

from typing import TYPE_CHECKING

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.bagel.bagel_operation import BagelOperation
from zzz_od.operation.compendium.compendium_choose_category import (
    CompendiumChooseCategory,
)

if TYPE_CHECKING:
    from one_dragon.base.operation.operation_round_result import OperationRoundResult
    from zzz_od.context.zzz_context import ZContext


class BagelOpenCompendium(BagelOperation):
    """从普通大世界打开快捷手册并进入贝果主界面。调用者负责准备入场前位置。"""

    def __init__(self, ctx: ZContext) -> None:
        """复用快捷手册列表区域，不执行副本传送确认。"""
        super().__init__(ctx, op_name='贝果-快捷手册入口', timeout_seconds=90)
        self.scroll_count: int = 0

    def handle_init(self) -> None:
        """每次执行重新计算卡片查找次数。"""
        super().handle_init()
        self.scroll_count = 0

    @operation_node(name='打开快捷手册作战页', is_start_node=True, timeout_seconds=30)
    def open_combat(self) -> OperationRoundResult:
        """使用通用画面路由打开作战页。"""
        return self.round_by_goto_screen(screen_name='快捷手册-作战')

    @node_from(from_name='打开快捷手册作战页')
    @operation_node(name='选择周期征讨', screenshot_before_round=False)
    def choose_category(self) -> OperationRoundResult:
        """复用快捷手册分类选择，下一节点重新读取卡片内容。"""
        operation = CompendiumChooseCategory(self.ctx, '周期征讨')
        operation.timeout_seconds = min(15, max(0, self.timeout_seconds - self.operation_usage_time))
        return self.round_by_op_result(operation.execute())

    @node_from(from_name='选择周期征讨')
    @operation_node(name='打开迷宫诡域', timeout_seconds=30)
    def open_bagel(self) -> OperationRoundResult:
        """标题与前往按钮必须属于同一卡片；点击后只等完整贝果入口。"""
        if self._at_bagel_hub():
            return self.round_success('已到贝果入口')
        if self.node_clicked:
            # 点卡片「前往」后可能先停在活动页（标题为「迷宫诡域：古怪试炼」并带赛季内容）。
            # 该页同样有「前往空洞」，点它进入贝果选图页；选图页没有主界面标题，
            # 所以这里只等「前往备战」出现，不能等主界面标题。
            return self.round_by_find_and_click_area(
                self.last_screenshot, '贝果-研究站', '前往空洞',
                until_find_all=[('贝果-选图', '前往备战')],
                success_wait=1, retry_wait=1,
            )
        if not self._has('TAB-作战', '快捷手册-作战'):
            return self.round_wait('等待快捷手册作战页', wait=0.5)
        titles_area = self.ctx.screen_loader.get_area('快捷手册', '副本列表')
        buttons_area = self.ctx.screen_loader.get_area('快捷手册', '前往列表')
        if titles_area is None or buttons_area is None:
            return self.round_fail('缺少快捷手册副本或前往列表区域')
        titles = self.ctx.ocr_service.get_ocr_result_list(
            image=self.last_screenshot, rect=titles_area.rect,
        )
        # 卡片标题在活动期间带副标题（如「迷宫诡域：古怪试炼」），只用前缀匹配，
        # 避免整串相等时找不到卡片而一直滚动。
        bagel_title = gt('迷宫诡域', 'game')
        target = next((item for item in titles
                       if str_utils.remove_whitespace(item.data).startswith(bagel_title)), None)
        if target is None:
            if self.scroll_count >= 5:
                return self.round_fail('快捷手册未找到迷宫诡域，停止并保留现场')
            self.scroll_count += 1
            # 迷宫诡域在周期征讨列表顶部，向下拖动可恢复上次留下的滚动位置。
            start = titles_area.center
            self.ctx.controller.drag_to(start=start, end=start + Point(0, 300))
            return self.round_wait('向上查找迷宫诡域卡片', wait=0.5)
        buttons = self.ctx.ocr_service.get_ocr_result_list(
            image=self.last_screenshot, rect=buttons_area.rect,
        )
        # 1080p 卡片中按钮在标题下约 100 像素；下一张卡片的按钮不在此范围。
        candidates = [item for item in buttons
                      if str_utils.remove_whitespace(item.data) == gt('前往', 'game')
                      and 0 < item.center.y - target.center.y <= 150]
        if len(candidates) != 1:
            return self.round_fail('无法确认迷宫诡域卡片的前往按钮，停止并保留现场')
        if not self.ctx.controller.click(candidates[0].center):
            return self.round_retry('点击迷宫诡域前往失败', wait=0.5)
        self.node_clicked = True
        return self.round_wait('已点击迷宫诡域前往，等待贝果主界面', wait=0.5)
