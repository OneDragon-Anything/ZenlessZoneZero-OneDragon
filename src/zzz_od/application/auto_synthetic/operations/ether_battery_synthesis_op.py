import time

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.operation.goto.goto_menu import GotoMenu
from zzz_od.application.auto_synthetic.auto_synthetic_config import AutoSyntheticConfig


class EtherBatterySynthesisOp(ZOperation):
    """电池合成操作 - 单一职责：处理电池合成的所有UI交互"""

    def __init__(self, ctx, config: AutoSyntheticConfig):
        ZOperation.__init__(self, ctx, op_name='电池合成')
        self.config = config
        self.max_synthetic_quantity: int = 0

    @operation_node(name='打开菜单', is_start_node=True)
    def goto_menu(self) -> OperationRoundResult:
        op = GotoMenu(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='打开菜单')
    @operation_node(name='计算最大合成数量')
    def check_charge_power(self) -> OperationRoundResult:
        """计算最大可合成数量"""
        area = self.ctx.screen_loader.get_area('菜单', '文本-电量')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        digit = str_utils.get_positive_digits(ocr_result, None)

        if digit is None:
            return self.round_retry('未识别到电量', wait=1)

        self.max_synthetic_quantity = int(digit / 60)
        if self.max_synthetic_quantity < 1:
            return self.round_success(status="电量不足")
        return self.round_success()

    @node_from(from_name='计算最大合成数量')
    @operation_node(name='前往合成')
    def goto_synthesis(self) -> OperationRoundResult:
        """前往电池合成界面"""
        return self.round_by_goto_screen(screen_name='仓库-材料道具-道具处理')

    @node_from(from_name='前往合成')
    @operation_node(name='选择电池')
    def select_battery(self) -> OperationRoundResult:
        """选择电池"""
        result = self.round_by_find_area(self.last_screenshot, '仓库-材料道具-道具处理', '文本-以太电池')
        if result.is_success:
            clicks = self.config.get_battery_click_count(self.max_synthetic_quantity)

            if clicks > 0 and not self._click_increase_button(clicks):
                return self.round_retry(status='未找到数量增加按钮', wait=1)
            return self.round_success(status='可合成')

        result = self.round_by_find_area(self.last_screenshot, '仓库-材料道具-道具处理', '图像-以太电池')
        if result.is_success:
            return self.round_success(status='电量不足')

        return self.round_retry(wait=1)

    def _click_increase_button(self, number: int) -> bool:
        """点击增加按钮"""
        area = self.ctx.screen_loader.get_area('仓库-材料道具-道具处理', '按钮-增加')
        if not area:
            return False

        for _ in range(number):
            self.ctx.controller.click(area.center)
            time.sleep(0.2)
        return True

    @node_from(from_name='选择电池', status='可合成')
    @operation_node(name='执行合成')
    def perform_synthesis(self) -> OperationRoundResult:
        """执行合成"""
        result = self.round_by_find_and_click_area(self.last_screenshot, '仓库-材料道具-道具处理', '按钮-合成')
        if result.is_success:
            return self.round_success()
        return self.round_retry(wait=1)

    @node_from(from_name='执行合成')
    @operation_node(name='确认合成')
    def confirm(self) -> OperationRoundResult:
        """确认合成"""
        result = self.round_by_find_and_click_area(self.last_screenshot, '仓库-材料道具-道具处理', '按钮-确认')
        if result.is_success:
            return self.round_success()
        return self.round_retry(wait=1)

    @node_from(from_name='选择电池', status='电量不足')
    @node_from(from_name='确认合成')
    @operation_node(name='完成')
    def complete(self) -> OperationRoundResult:
        """完成合成"""
        return self.round_success()