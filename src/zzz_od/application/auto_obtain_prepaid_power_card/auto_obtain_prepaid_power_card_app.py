import time
from typing import Optional
from cv2.typing import MatLike

from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from zzz_od.application.auto_obtain_prepaid_power_card import auto_obtain_prepaid_power_card_const
from zzz_od.application.auto_obtain_prepaid_power_card.auto_obtain_prepaid_power_card_config import \
    AutoObtainPrepaidPowerCardConfig, UseTheme
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class AutoObtainPrepaidPowerCardApp(ZApplication):

    TASK_OUTPOST_LOGISTICS = "后勤商店"
    TASK_MONTHLY_RESTOCK = "情报板商店"
    TASK_FADING_SIGNAL = "信号残响"

    def __init__(self, ctx: ZContext) -> None:
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=auto_obtain_prepaid_power_card_const.APP_ID,
            op_name=auto_obtain_prepaid_power_card_const.APP_NAME,
        )

        self.config: AutoObtainPrepaidPowerCardConfig = self.ctx.run_context.get_config(
            app_id=auto_obtain_prepaid_power_card_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        # 任务队列和状态
        self._task_queue: list[str] = []
        self._current_task_index: int = 0
        self._task_results: dict[str, str] = {}
        self._max_outpost_logistics_obtain_quantity: int = 0
        self._max_monthly_restock_obtain_quantity: int = 0
        self._max_fading_signal_obtain_quantity: int = 0

    @operation_node(name='检查配置', is_start_node=True)
    def check_config(self) -> OperationRoundResult:
        """
        检查配置，构建任务队列
        """
        # 清空并重新构建任务队列
        self._task_queue: list[str] = []

        if self.config.outpost_logistics:
            self._task_queue.append(self.TASK_OUTPOST_LOGISTICS)
        if self.config.monthly_restock:
            self._task_queue.append(self.TASK_MONTHLY_RESTOCK)
        if self.config.fading_signal:
            self._task_queue.append(self.TASK_FADING_SIGNAL)
        # 后续可以在这里添加其他兑换储值电卡的渠道

        if not self._task_queue:
            return self.round_success(status='无需获取')

        # 重置任务索引
        self._current_task_index: int = 0
        self._task_results: dict[str, str] = {}

        # 开始执行第一个任务
        return self._execute_current_task()

    def _execute_current_task(self) -> OperationRoundResult:
        """
        根据当前任务类型返回对应的状态
        """
        if self._current_task_index >= len(self._task_queue):
            return self.round_success(status='全部完成')

        current_task = self._task_queue[self._current_task_index]

        if current_task == self.TASK_OUTPOST_LOGISTICS:
            return self.round_success(status='后勤商店')
        elif current_task == self.TASK_MONTHLY_RESTOCK:
            if self.config.use_theme == UseTheme.DEFAULT.value.value:
                return self.round_success(status='使用常规主题')
            return self.round_success(status='情报板商店')
        elif current_task == self.TASK_FADING_SIGNAL:
            return self.round_success(status='信号残响')
        else:
            return self.round_fail(f'未知任务类型: {current_task}')

    # ==================== 后勤商店相关节点 ====================

    @node_from(from_name='检查配置', status='后勤商店')
    @operation_node(name='后勤商店-前往')
    def goto_outpost_logistics(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='快捷手册-作战-后勤商店')

    @node_from(from_name='后勤商店-前往')
    @operation_node(name='后勤商店-计算最大获取数量')
    def outpost_logistics_calculate_max_quantity(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('快捷手册-作战-后勤商店', '文本-零号业绩')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        digit = str_utils.get_positive_digits(ocr_result, None)
        if digit is None:
            return self.round_retry('未识别到零号业绩', wait=1)

        self._max_outpost_logistics_obtain_quantity = int(digit / 120)
        if self._max_outpost_logistics_obtain_quantity < 1:
            return self.round_success(status="零号业绩不足")
        return self.round_success(f'在后勤商店可以获取的储值电卡数量为： {self._max_outpost_logistics_obtain_quantity}个')

    @node_from(from_name='后勤商店-计算最大获取数量')
    @operation_node(name='后勤商店-选择储值电卡')
    def outpost_logistics_select(self) -> OperationRoundResult:
        """选择储值电卡"""
        # 第一步：尝试点击"储值电卡"文本区域
        result = self.round_by_find_and_click_area(self.last_screenshot, '快捷手册-作战-后勤商店', '文本-储值电卡')
        if result.is_success:
            time.sleep(0.5)
            return self.round_success(status=result.status)

        # 第二步：尝试识别储值电卡图片，最多滚动3次
        max_scrolls = 3
        for i in range(max_scrolls):
            mr = self.get_pos_by_outpost_logistics_prepaid_power_card(self.screenshot())

            if mr is not None:
                # 找到储值电卡图片，说明已售罄
                return self.round_success(status='已售罄')

            # 如果不是最后一次尝试，就向下滚动
            if i < max_scrolls - 1:
                self.ctx.controller.scroll(1)
                time.sleep(2)

        return self.round_retry(wait=1)

    def get_pos_by_outpost_logistics_prepaid_power_card(self, screen: MatLike) -> Optional[MatchResult]:
        """
        根据图像匹配
        @param screen: 游戏画面
        @return:
        """
        area = self.ctx.screen_loader.get_area('快捷手册-作战-后勤商店', '道具列表')
        part = cv2_utils.crop_image_only(screen, area.rect)

        mr = self.ctx.tm.match_one_by_feature(
            part, 'manage_item', 'prepaid_power_card', knn_distance_percent=0.5)
        if mr is None:
            return None

        mr.add_offset(area.left_top)
        return mr

    @node_from(from_name='后勤商店-选择储值电卡')
    @operation_node(name='后勤商店-选择获取数量')
    def outpost_logistics_select_quantity(self) -> OperationRoundResult:
        """选择储值电卡数量"""
        result = self.round_by_find_area(self.last_screenshot, '快捷手册-作战-后勤商店', '按钮-增加')
        if result.is_success:
            time.sleep(0.5)
            max_clicks = self._max_outpost_logistics_obtain_quantity - 1
            clicks = min(self.config.outpost_logistics_obtain_number, max_clicks)
            if clicks > 0 and not self.battery_select_number(clicks):
                return self.round_retry(status='未找到数量增加按钮', wait=1)
            return self.round_success(status='可获取')

        return self.round_retry(wait=1)

    def battery_select_number(self, number: int) -> bool:
        # 先找到目标区域
        area = self.ctx.screen_loader.get_area('快捷手册-作战-后勤商店', '按钮-增加')
        if not area:
            return False

        # 多次点击
        for _ in range(number):
            self.ctx.controller.click(area.center)
            time.sleep(0.2)  # 每次点击间隔
        return True

    @node_from(from_name='后勤商店-选择获取数量', status='可获取')
    @operation_node(name='后勤商店-确认')
    def outpost_logistics_confirm(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(self.last_screenshot, '快捷手册-作战-后勤商店', '按钮-确认')
        if result.is_success:
            return self.round_success(result.status, wait=1)
        return self.round_retry(wait=1)

    @node_from(from_name='后勤商店-计算最大获取数量', status='零号业绩不足')
    @node_from(from_name='后勤商店-选择储值电卡', status='已售罄')
    @node_from(from_name='后勤商店-确认')
    @operation_node(name='后勤商店-返回大世界')
    def outpost_logistics_return(self) -> OperationRoundResult:
        """返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='后勤商店-返回大世界')
    @operation_node(name='后勤商店-完成')
    def outpost_logistics_complete(self) -> OperationRoundResult:
        """后勤商店完成，检查下一个任务"""
        self._task_results[self.TASK_OUTPOST_LOGISTICS] = '完成'
        self._current_task_index += 1

        # 检查是否还有下一个任务
        if self._current_task_index < len(self._task_queue):
            next_task = self._task_queue[self._current_task_index]
            if next_task == self.TASK_MONTHLY_RESTOCK:
                if self.config.use_theme == UseTheme.DEFAULT.value.value:
                    return self.round_success(status='使用常规主题')
                return self.round_success(status='情报板商店')
            if next_task == self.TASK_FADING_SIGNAL:
                return self.round_success(status='信号残响')

        return self.round_success(status='全部完成')

    # ==================== 情报板商店相关节点 ====================

    @node_from(from_name='检查配置', status='情报板商店')
    @node_from(from_name='后勤商店-完成', status='情报板商店')
    @operation_node(name='情报板商店-前往主题界面')
    def goto_theme(self) -> OperationRoundResult:
        # 目前只适配了功能导览的默认主题
        return self.round_by_goto_screen(screen_name='功能导览-导览套件')

    @node_from(from_name='情报板商店-前往主题界面')
    @operation_node(name='情报板商店-使用常规主题')
    def use_conventional_theme(self) -> OperationRoundResult:
        if self.config.use_theme == UseTheme.DEFAULT.value.value:
            result = self.round_by_find_area(self.last_screenshot, '功能导览-导览套件', '文本-常规主题')
            if result.is_success:
                time.sleep(0.5)
                self.round_by_find_and_click_area(self.last_screenshot, '功能导览-导览套件', '左上角返回')
                return self.round_success(status=result.status)

        result = self.round_by_find_and_click_area(self.last_screenshot, '功能导览-导览套件', '图像-常规主题')
        if result.is_success:
            time.sleep(0.5)
            self.round_by_find_and_click_area(self.last_screenshot, '功能导览-导览套件', '按钮-装配')
            time.sleep(0.5)
            self.round_by_find_and_click_area(self.last_screenshot, '功能导览-导览套件', '左上角返回')
            return self.round_success(status=result.status)

        return self.round_retry(wait=1)

    @node_from(from_name='检查配置', status='使用常规主题')
    @node_from(from_name='后勤商店-完成', status='使用常规主题')
    @node_from(from_name='情报板商店-使用常规主题')
    @operation_node(name='情报板商店-前往')
    def goto_monthly_restock(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='情报板-点数兑换-情报板商店')

    @node_from(from_name='情报板商店-前往')
    @operation_node(name='情报板商店-计算最大获取数量')
    def monthly_restock_calculate_max_quantity(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('快捷手册-作战-后勤商店', '文本-零号业绩')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        digit = str_utils.get_positive_digits(ocr_result, None)
        if digit is None:
            return self.round_retry('未识别到贡献点数', wait=1)

        self._max_outpost_logistics_obtain_quantity = int(digit / 120)
        if self._max_outpost_logistics_obtain_quantity < 1:
            return self.round_success(status="贡献点数不足")
        return self.round_success(
            f'在情报板商店可以获取的储值电卡数量为： {self._max_outpost_logistics_obtain_quantity}个')

    @node_from(from_name='情报板商店-计算最大获取数量')
    @operation_node(name='情报板商店-选择储值电卡')
    def monthly_restock_select(self) -> OperationRoundResult:
        """选择储值电卡"""
        # 第一步：尝试点击"储值电卡"文本区域
        result = self.round_by_find_and_click_area(self.last_screenshot, '快捷手册-作战-后勤商店', '文本-储值电卡')
        if result.is_success:
            time.sleep(0.5)
            return self.round_success(status=result.status)

        # 没有已售罄的截图，下面没有实现
        # 第二步：尝试识别储值电卡图片，最多滚动3次
        # max_scrolls = 3
        # for i in range(max_scrolls):
        #     mr = self.get_pos_by_monthly_restock_prepaid_power_card(self.screenshot())
        #
        #     if mr is not None:
        #         # 找到储值电卡图片，说明已售罄
        #         return self.round_success(status='已售罄')
        #
        #     # 如果不是最后一次尝试，就向下滚动
        #     if i < max_scrolls - 1:
        #         self.ctx.controller.scroll(1)
        #         time.sleep(2)

        return self.round_retry(wait=1)

    # def get_pos_by_monthly_restock_prepaid_power_card(self, screen: MatLike) -> Optional[MatchResult]:
    #     """
    #     根据图像匹配
    #     @param screen: 游戏画面
    #     @return:
    #     """
    #     area = self.ctx.screen_loader.get_area('快捷手册-作战-后勤商店', '道具列表')
    #     part = cv2_utils.crop_image_only(screen, area.rect)
    #
    #     mr = self.ctx.tm.match_one_by_feature(part, 'monthly_restock', 'prepaid_power_card', knn_distance_percent=0.5)
    #     if mr is None:
    #         return None
    #
    #     mr.add_offset(area.left_top)
    #     return mr

    @node_from(from_name='情报板商店-选择储值电卡')
    @operation_node(name='情报板商店-选择获取数量')
    def monthly_restock_select_quantity(self) -> OperationRoundResult:
        """选择储值电卡数量"""
        result = self.round_by_find_area(self.last_screenshot, '快捷手册-作战-后勤商店', '按钮-增加')
        if result.is_success:
            time.sleep(0.5)
            max_clicks = self._max_monthly_restock_obtain_quantity - 1
            clicks = min(self.config.monthly_restock_obtain_number, max_clicks)
            if clicks > 0 and not self.battery_select_number(clicks):
                return self.round_retry(status='未找到数量增加按钮', wait=1)
            return self.round_success(status='可获取')

        return self.round_retry(wait=1)

    @node_from(from_name='情报板商店-选择获取数量', status='可获取')
    @operation_node(name='情报板商店-确认')
    def monthly_restock_confirm(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(self.last_screenshot, '快捷手册-作战-后勤商店', '按钮-确认')
        if result.is_success:
            return self.round_success(result.status, wait=1)
        return self.round_retry(wait=1)

    @node_from(from_name='情报板商店-计算最大获取数量', status='贡献点数不足')
    @node_from(from_name='情报板商店-选择储值电卡', status='已售罄')
    @node_from(from_name='情报板商店-确认')
    @operation_node(name='情报板商店-返回大世界')
    def monthly_restock_return(self) -> OperationRoundResult:
        """返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='情报板商店-返回大世界')
    @operation_node(name='情报板商店-完成')
    def monthly_restock_complete(self) -> OperationRoundResult:
        """情报板商店完成，检查下一个任务"""
        self._task_results[self.TASK_MONTHLY_RESTOCK] = '完成'
        self._current_task_index += 1

        # 检查是否还有下一个任务
        if self._current_task_index < len(self._task_queue):
            next_task = self._task_queue[self._current_task_index]
            if next_task == self.TASK_FADING_SIGNAL:
                return self.round_success(status='信号残响')
            if next_task == self.TASK_OUTPOST_LOGISTICS:
                return self.round_success(status='后勤商店')

        return self.round_success(status='全部完成')

    # ==================== 信号残响相关节点 ====================

    @node_from(from_name='检查配置', status='信号残响')
    @node_from(from_name='后勤商店-完成', status='信号残响')
    @node_from(from_name='情报板商店-完成', status='信号残响')
    @operation_node(name='信号残响-前往')
    def goto_fading_signal(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='信号残响')

    @node_from(from_name='信号残响-前往')
    @operation_node(name='信号残响-计算最大获取数量')
    def fading_signal_calculate_max_quantity(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('信号残响', '文本-信号残响')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        digit = str_utils.get_positive_digits(ocr_result, None)
        if digit is None:
            return self.round_retry('未识别到信号残响', wait=1)

        self._max_fading_signal_obtain_quantity = int(digit / 50)
        if self._max_fading_signal_obtain_quantity < 1:
            return self.round_success(status="信号残响不足")
        return self.round_success(
            f'在信号残响可以获取的储值电卡数量为： {self._max_fading_signal_obtain_quantity}个')

    @node_from(from_name='信号残响-计算最大获取数量')
    @operation_node(name='信号残响-选择储值电卡')
    def fading_signal_select(self) -> OperationRoundResult:
        """选择储值电卡"""
        # 第一步：尝试点击"储值电卡"文本区域
        result = self.round_by_find_and_click_area(self.last_screenshot, '信号残响', '文本-储值电卡')
        if result.is_success:
            time.sleep(0.5)
            return self.round_success(status=result.status)

        # 第二步：尝试识别储值电卡图片，最多滚动3次
        max_scrolls = 3
        for i in range(max_scrolls):
            mr = self.get_pos_by_fading_signal_prepaid_power_card(self.screenshot())

            if mr is not None:
                # 找到储值电卡图片，说明已售罄
                return self.round_success(status='已售罄')

            # 如果不是最后一次尝试，就向下滚动
            if i < max_scrolls - 1:
                self.ctx.controller.scroll(1)
                time.sleep(2)

        return self.round_retry(wait=1)

    def get_pos_by_fading_signal_prepaid_power_card(self, screen: MatLike) -> Optional[MatchResult]:
        """
        根据图像匹配
        @param screen: 游戏画面
        @return:
        """
        area = self.ctx.screen_loader.get_area('信号残响', '道具列表')
        part = cv2_utils.crop_image_only(screen, area.rect)

        mr = self.ctx.tm.match_one_by_feature(
            part, 'fading_signal', 'prepaid_power_card', knn_distance_percent=0.5)
        if mr is None:
            return None

        mr.add_offset(area.left_top)
        return mr

    @node_from(from_name='信号残响-选择储值电卡')
    @operation_node(name='信号残响-选择获取数量')
    def fading_signal_select_quantity(self) -> OperationRoundResult:
        """选择储值电卡数量"""
        result = self.round_by_find_area(self.last_screenshot, '快捷手册-作战-后勤商店', '按钮-增加')
        if result.is_success:
            time.sleep(0.5)
            max_clicks = self._max_fading_signal_obtain_quantity - 1
            clicks = min(self.config.fading_signal_obtain_number, max_clicks)
            if clicks > 0 and not self.battery_select_number(clicks):
                return self.round_retry(status='未找到数量增加按钮', wait=1)
            return self.round_success(status='可获取')

        return self.round_retry(wait=1)

    @node_from(from_name='信号残响-选择获取数量', status='可获取')
    @operation_node(name='信号残响-确认')
    def fading_signal_confirm(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '快捷手册-作战-后勤商店', '按钮-确认')
        if result.is_success:
            return self.round_success(result.status, wait=1)
        return self.round_retry(wait=1)

    @node_from(from_name='信号残响-计算最大获取数量', status='贡献点数不足')
    @node_from(from_name='信号残响-选择储值电卡', status='已售罄')
    @node_from(from_name='信号残响-确认')
    @operation_node(name='信号残响-返回大世界')
    def fading_signal_return(self) -> OperationRoundResult:
        """返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='信号残响-返回大世界')
    @operation_node(name='信号残响-完成')
    def fading_signal_complete(self) -> OperationRoundResult:
        """信号残响完成，检查下一个任务"""
        self._task_results[self.TASK_FADING_SIGNAL] = '完成'
        self._current_task_index += 1

        # 检查是否还有下一个任务
        if self._current_task_index < len(self._task_queue):
            next_task = self._task_queue[self._current_task_index]
            if next_task == self.TASK_OUTPOST_LOGISTICS:
                return self.round_success(status='后勤商店')
            if next_task == self.TASK_MONTHLY_RESTOCK:
                if self.config.use_theme == UseTheme.DEFAULT.value.value:
                    return self.round_success(status='使用常规主题')
                return self.round_success(status='情报板商店')

        return self.round_success(status='全部完成')

    # ==================== 最终返回节点 ====================

    @node_from(from_name='后勤商店-完成', status='全部完成')
    @node_from(from_name='情报板商店-完成', status='全部完成')
    @node_from(from_name='信号残响-完成', status='全部完成')
    @node_from(from_name='检查配置', status='无需获取')
    @operation_node(name='最终返回')
    def final_return(self) -> OperationRoundResult:
        """最终返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

