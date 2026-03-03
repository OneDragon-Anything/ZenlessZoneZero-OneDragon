import time
from typing import Optional

from cv2.typing import MatLike

from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.zzz_operation import ZOperation


class MonthlyRestockOperation(ZOperation):
    """情报板商店操作"""

    def __init__(self, ctx, config):
        ZOperation.__init__(self, ctx, op_name='情报板商店')
        self.config = config
        self._max_quantity: int = 0

    # ==================== 主题相关节点 ====================

    @operation_node(name='前往功能导览', is_start_node=True)
    def goto_function_menu(self) -> OperationRoundResult:
        """前往主功能导览"""
        return self.round_by_goto_screen(screen_name='功能导览')

    @node_from(from_name='前往功能导览')
    @operation_node(name='检查使用主题')
    def check_use_theme(self) -> OperationRoundResult:
        """检查是否在常规主题"""
        result = self.round_by_find_area(self.last_screenshot, '功能导览-常规', 'TAB-常规主题')
        if result.is_success:
            time.sleep(0.5)
            return self.round_success(status="常规主题")
        else:
            return self.round_success(status="其他主题")

    @node_from(from_name='检查使用主题', status="其他主题")
    @operation_node(name='点击底部导览套件')
    def click_guide_kit(self) -> OperationRoundResult:
        """点击底部导览套件进入导览套件界面"""
        result = self.round_by_find_and_click_area(
            self.last_screenshot, '功能导览-常规', '底部-导览套件'
        )
        if result.is_success:
            time.sleep(1)  # 等待界面切换
            return self.round_success(status='已点击导览套件')
        return self.round_retry(wait=1)

    @node_from(from_name='点击底部导览套件', status="已点击导览套件")
    @operation_node(name='使用常规主题')
    def use_default_theme(self) -> OperationRoundResult:
        """使用常规主题"""
        result = self.round_by_find_and_click_area(
            self.last_screenshot, '功能导览-导览套件', '图像-常规主题'
        )
        if result.is_success:
            time.sleep(0.5)
            self.round_by_find_and_click_area(
                self.last_screenshot, '功能导览-导览套件', '按钮-装配'
            )
            time.sleep(0.5)
            self.round_by_find_and_click_area(
                self.last_screenshot, '功能导览-导览套件', '左上角返回'
            )
            return self.round_success(status=result.status)

        return self.round_retry(wait=1)

    # ==================== 商店导航节点 ====================

    @node_from(from_name='检查使用主题', status='常规主题')
    @node_from(from_name='使用常规主题')
    @operation_node(name='点击情报板文本')
    def click_info_board_text(self) -> OperationRoundResult:
        """点击情报板文本"""
        result = self.round_by_find_and_click_area(
            self.last_screenshot, '功能导览-常规', '文本-情报板'
        )
        if result.is_success:
            time.sleep(1)
            return self.round_success(status='已点击情报板')
        return self.round_retry(wait=1)

    @node_from(from_name='点击情报板文本')
    @operation_node(name='进入情报板')
    def enter_info_board(self) -> OperationRoundResult:
        """确认进入情报板"""
        result = self.round_by_find_area(self.last_screenshot, '情报板', 'TAB-情报板')
        if result.is_success:
            return self.round_success(status='已进入情报板')
        return self.round_retry(wait=1)

    @node_from(from_name='进入情报板')
    @operation_node(name='点击点数兑换')
    def click_point_exchange(self) -> OperationRoundResult:
        """点击点数兑换"""
        result = self.round_by_find_and_click_area(
            self.last_screenshot, '情报板', '点数兑换'
        )
        if result.is_success:
            time.sleep(1)
            return self.round_success(status='已点击点数兑换')
        return self.round_retry(wait=1)

    # ==================== 商店操作节点 ====================

    @node_from(from_name='点击点数兑换')
    @operation_node(name='计算最大获取数量')
    def calculate_max_quantity(self) -> OperationRoundResult:
        """计算最大获取数量"""
        area = self.ctx.screen_loader.get_area('情报板-点数兑换-情报板商店', '文本-贡献点数')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        digit = str_utils.get_positive_digits(ocr_result, None)

        if digit is None:
            return self.round_retry('未识别到贡献点数', wait=1)

        self._max_quantity = int(digit / 120)

        if self._max_quantity < 1:
            return self.round_success(status="贡献点数不足")

        return self.round_success(f'在情报板商店可以获取的储值电卡数量为：{self._max_quantity}个')

    @node_from(from_name='计算最大获取数量')
    @operation_node(name='选择储值电卡')
    def select_prepaid_card(self) -> OperationRoundResult:
        """选择储值电卡"""
        result = self.round_by_find_and_click_area(
            self.last_screenshot, '情报板-点数兑换-情报板商店', '文本-储值电卡'
        )
        if result.is_success:
            time.sleep(0.5)
            return self.round_success(status=result.status)

        # # 滚动查找图片
        # max_scrolls = 3
        # for i in range(max_scrolls):
        #     mr = self._get_prepaid_card_position(self.screenshot())
        #
        #     if mr is not None:
        #         return self.round_success(status='已售罄')
        #
        #     if i < max_scrolls - 1:
        #         self.ctx.controller.scroll(1)
        #         time.sleep(2)

        return self.round_retry(wait=1)

    # def _get_prepaid_card_position(self, screen: MatLike) -> Optional[MatchResult]:
    #     """获取储值电卡位置"""
    #     area = self.ctx.screen_loader.get_area('情报板-点数兑换-情报板商店', '道具列表')
    #     part = cv2_utils.crop_image_only(screen, area.rect)
    #
    #     mr = self.ctx.tm.match_one_by_feature(
    #         part, 'monthly_restock', 'prepaid_power_card', knn_distance_percent=0.5
    #     )
    #     if mr is None:
    #         return None
    #
    #     mr.add_offset(area.left_top)
    #     return mr

    @node_from(from_name='选择储值电卡')
    @operation_node(name='选择获取数量')
    def select_quantity(self) -> OperationRoundResult:
        """选择获取数量"""
        result = self.round_by_find_area(
            self.last_screenshot, '快捷手册-作战-后勤商店', '按钮-增加'
        )
        if result.is_success:
            time.sleep(0.5)
            max_clicks = self._max_quantity - 1
            clicks = min(self.config.monthly_restock_obtain_number, max_clicks)
            if clicks > 0 and not self._click_increase_button(clicks):
                return self.round_retry(status='未找到数量增加按钮', wait=1)
            return self.round_success(status='可获取')

        return self.round_retry(wait=1)

    def _click_increase_button(self, number: int) -> bool:
        """点击增加按钮"""
        area = self.ctx.screen_loader.get_area('快捷手册-作战-后勤商店', '按钮-增加')
        if not area:
            return False

        for _ in range(number):
            self.ctx.controller.click(area.center)
            time.sleep(0.2)
        return True

    @node_from(from_name='选择获取数量', status='可获取')
    @operation_node(name='确认')
    def confirm_purchase(self) -> OperationRoundResult:
        """确认购买"""
        result = self.round_by_find_and_click_area(
            self.last_screenshot, '快捷手册-作战-后勤商店', '按钮-确认'
        )
        if result.is_success:
            return self.round_success(result.status, wait=1)
        return self.round_retry(wait=1)

    @node_from(from_name='计算最大获取数量', status='贡献点数不足')
    @node_from(from_name='选择储值电卡', status='已售罄')
    @node_from(from_name='确认')
    @operation_node(name='返回大世界')
    def return_to_world(self) -> OperationRoundResult:
        """返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='返回大世界')
    @operation_node(name='完成')
    def complete(self) -> OperationRoundResult:
        """完成"""
        return self.round_success()