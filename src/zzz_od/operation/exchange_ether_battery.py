from typing import ClassVar

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class ExchangeEtherBattery(ZOperation):
    """
    从快捷手册资源栏进入以太电池合成，并完成电池兑换。
    """

    STATUS_MATERIAL_NOT_ENOUGH: ClassVar[str] = '合成素材不足'
    STATUS_EXCHANGE_SUCCESS: ClassVar[str] = '兑换以太电池成功'

    def __init__(self, ctx: ZContext) -> None:
        ZOperation.__init__(
            self,
            ctx=ctx,
            op_name='兑换以太电池',
            node_max_retry_times=5,
        )

    @operation_node(name='点击以太电池', is_start_node=True)
    def click_ether_battery(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '快捷手册',
            '以太电池',
            success_wait=1,
            retry_wait=0.5,
        )

    @node_from(from_name='点击以太电池')
    @operation_node(name='点击合成入口')
    def click_synthesize_entry(self) -> OperationRoundResult:
        return self.round_by_ocr_and_click(
            self.last_screenshot,
            '合成',
            success_wait=1,
            retry_wait=0.5,
        )

    @node_from(from_name='点击合成入口')
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
