import time
from typing import ClassVar

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class ExchangeEtherBattery(ZOperation):
    """
    在仓库的道具处理页中，将自然恢复的电量兑换为以太电池。
    """

    STATUS_NOT_ENABLED: ClassVar[str] = '未开启'
    STATUS_ETHER_BATTERY_NOT_FOUND: ClassVar[str] = '未找到以太电池'
    STATUS_MATERIAL_NOT_ENOUGH: ClassVar[str] = '合成素材不足'
    STATUS_EXCHANGE_SUCCESS: ClassVar[str] = '兑换以太电池成功'

    GRID_ROW_COUNT: ClassVar[int] = 5
    GRID_COL_COUNT: ClassVar[int] = 8
    MAX_SCROLL_COUNT: ClassVar[int] = 5

    def __init__(self, ctx: ZContext) -> None:
        ZOperation.__init__(
            self,
            ctx=ctx,
            op_name='兑换以太电池',
            node_max_retry_times=5,
        )
        self.scroll_count: int = 0

    def _ocr_detail_title(self) -> str:
        area = self.ctx.screen_loader.get_area('道具处理', '详情标题')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        return self.ctx.ocr.run_ocr_single_line(part)

    def _is_ether_battery_selected(self) -> bool:
        title = self._ocr_detail_title()
        return str_utils.find_by_lcs(gt('以太电池', 'game'), title, percent=0.6)

    def _iter_item_grid_points(self) -> list[Point]:
        grid_area = self.ctx.screen_loader.get_area('道具处理', '道具格子区域')
        if grid_area is None:
            return []

        points: list[Point] = []
        col_width = grid_area.width / self.GRID_COL_COUNT
        row_height = grid_area.height / self.GRID_ROW_COUNT
        for row in range(self.GRID_ROW_COUNT):
            for col in range(self.GRID_COL_COUNT):
                points.append(Point(
                    int(grid_area.x1 + col_width * (col + 0.5)),
                    int(grid_area.y1 + row_height * (row + 0.5)),
                ))
        return points

    @operation_node(name='前往材料道具页', is_start_node=True)
    def goto_material_items(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='仓库-材料道具', retry_wait=1)

    @node_from(from_name='前往材料道具页')
    @operation_node(name='打开道具处理')
    def open_item_processing(self) -> OperationRoundResult:
        screen_result = self.round_by_find_area(
            self.last_screenshot,
            '道具处理',
            '标题-道具处理',
        )
        if screen_result.is_success:
            return self.round_success('道具处理', wait=0.3)

        click_result = self.round_by_find_and_click_area(
            self.last_screenshot,
            '仓库-材料道具',
            '按钮-道具处理',
            success_wait=1,
            retry_wait=0.5,
        )
        if click_result.is_success:
            return self.round_retry('等待道具处理', wait=1)
        return click_result

    @node_from(from_name='打开道具处理')
    @operation_node(name='选择以太电池', node_max_retry_times=6)
    def choose_ether_battery(self) -> OperationRoundResult:
        if self._is_ether_battery_selected():
            return self.round_success('以太电池', wait=0.3)

        for point in self._iter_item_grid_points():
            self.ctx.controller.click(point)
            time.sleep(0.2)
            self.screenshot()
            if self._is_ether_battery_selected():
                return self.round_success('以太电池', wait=0.3)

        if self.scroll_count >= self.MAX_SCROLL_COUNT:
            return self.round_fail(self.STATUS_ETHER_BATTERY_NOT_FOUND)

        self.scroll_count += 1
        self.scroll_area('道具处理', '道具列表', direction='down', start_ratio=0.85, end_ratio=0.2)
        return self.round_retry(self.STATUS_ETHER_BATTERY_NOT_FOUND, wait=0.8)

    @node_from(from_name='选择以太电池')
    @operation_node(name='检查合成素材')
    def check_material(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '道具处理', '合成素材不足')
        if result.is_success:
            return self.round_success(self.STATUS_MATERIAL_NOT_ENOUGH, wait=0.3)
        return self.round_success()

    @node_from(from_name='检查合成素材', ignore_status=False)
    @operation_node(name='设置最大合成数量')
    def set_max_amount(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('道具处理', '滑块-合成数量')
        if area is None:
            return self.round_fail('区域未配置 滑块-合成数量')

        start = Point(area.x1 + 30, area.center.y)
        end = Point(area.x2 - 10, area.center.y)
        self.ctx.controller.drag_to(start=start, end=end, duration=0.5)
        return self.round_success(wait=0.5)

    @node_from(from_name='设置最大合成数量')
    @operation_node(name='点击合成')
    def click_synthesize(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '道具处理',
            '按钮-合成',
            success_wait=1,
            retry_wait=0.5,
        )

    @node_from(from_name='点击合成')
    @operation_node(name='确认合成')
    def confirm_synthesize(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '道具处理-合成确认',
            '按钮-确认',
            success_wait=1,
            retry_wait=0.5,
        )

    @node_from(from_name='确认合成')
    @operation_node(name='确认获得')
    def confirm_obtained(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '道具处理-获得', '标题-获得')
        if result.is_success:
            return self.round_by_find_and_click_area(
                self.last_screenshot,
                '道具处理-获得',
                '按钮-确认',
                success_wait=0.8,
                retry_wait=0.5,
            )

        result = self.round_by_find_area(self.last_screenshot, '道具处理', '标题-道具处理')
        if result.is_success:
            return self.round_success(self.STATUS_EXCHANGE_SUCCESS, wait=0.3)

        return self.round_retry('等待获得弹窗', wait=0.5)

    @node_from(from_name='检查合成素材', status=STATUS_MATERIAL_NOT_ENOUGH)
    @node_from(from_name='确认获得')
    @operation_node(name='兑换完成')
    def finish_exchange(self) -> OperationRoundResult:
        if self.previous_node.status == self.STATUS_MATERIAL_NOT_ENOUGH:
            return self.round_success(self.STATUS_MATERIAL_NOT_ENOUGH)
        return self.round_success(self.STATUS_EXCHANGE_SUCCESS)
