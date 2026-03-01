import time
from typing import List, Dict

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from zzz_od.application.auto_synthetic import auto_synthetic_const
from zzz_od.application.auto_synthetic.auto_synthetic_config import AutoSyntheticConfig
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.goto.goto_menu import GotoMenu
from zzz_od.operation.transport import Transport
from zzz_od.operation.wait_normal_world import WaitNormalWorld


class AutoSyntheticApp(ZApplication):
    # 定义所有可能的任务类型
    TASK_HIFI_MASTER = '母盘合成'
    TASK_ETHER_BATTERY = '电池合成'

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=auto_synthetic_const.APP_ID,
            op_name=auto_synthetic_const.APP_NAME,
        )
        self.config: AutoSyntheticConfig = self.ctx.run_context.get_config(
            app_id=auto_synthetic_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        # 任务队列和状态
        self._task_queue: List[str] = []
        self._current_task_index: int = 0
        self._task_results: Dict[str, str] = {}
        self._max_source_ether_battery_synthetic_quantity: int = 0

    @operation_node(name='检查配置', is_start_node=True)
    def check_config(self) -> OperationRoundResult:
        """
        检查配置，构建任务队列
        """
        # 清空并重新构建任务队列
        self._task_queue: List[str] = []

        if self.config.hifi_master_copy:
            self._task_queue.append(self.TASK_HIFI_MASTER)
        if self.config.source_ether_battery:
            self._task_queue.append(self.TASK_ETHER_BATTERY)
        # 后续可以在这里添加其他合成任务

        if not self._task_queue:
            return self.round_success(status='无需合成')

        # 重置任务索引
        self._current_task_index: int = 0
        self._task_results: Dict[str, str] = {}

        # 开始执行第一个任务
        return self._execute_current_task()

    def _execute_current_task(self) -> OperationRoundResult:
        """
        根据当前任务类型返回对应的状态
        """
        if self._current_task_index >= len(self._task_queue):
            return self.round_success(status='全部完成')

        current_task = self._task_queue[self._current_task_index]

        if current_task == self.TASK_HIFI_MASTER:
            return self.round_success(status='执行母盘合成')
        elif current_task == self.TASK_ETHER_BATTERY:
            return self.round_success(status='执行电池合成')
        else:
            return self.round_fail(f'未知任务类型: {current_task}')

    # ==================== 母盘合成相关节点 ====================

    @node_from(from_name='检查配置', status='执行母盘合成')
    @operation_node(name='母盘-传送')
    def hifi_transport(self) -> OperationRoundResult:
        """前往音像店"""
        op = Transport(self.ctx, '六分街', '音像店', wait_at_last=False)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='母盘-传送')
    @operation_node(name='母盘-等待加载')
    def hifi_wait_loading(self) -> OperationRoundResult:
        """等待加载"""
        result = self.round_by_find_area(self.last_screenshot, '音像店', '合成')
        if result.is_success:
            return self.round_success(result.status)

        op = WaitNormalWorld(self.ctx, check_once=True)
        result = self.round_by_op_result(op.execute())
        if result.is_success:
            return self.round_success(result.status)

        return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='母盘-等待加载')
    @operation_node(name='母盘-移动交互')
    def hifi_move_interact(self) -> OperationRoundResult:
        """移动交互"""
        self.ctx.controller.move_w(press=True, press_time=1, release=True)
        time.sleep(1)
        self.ctx.controller.interact(press=True, press_time=0.2, release=True)
        return self.round_success()

    @node_from(from_name='母盘-等待加载', status='合成')
    @node_from(from_name='母盘-移动交互')
    @operation_node(name='母盘-打开合成')
    def hifi_open_synthesis(self) -> OperationRoundResult:
        """打开合成界面"""
        result = self.round_by_find_and_click_area(self.last_screenshot, '音像店', '合成')
        if result.is_success:
            return self.round_success(result.status, wait=1)
        return self.round_retry(wait=1)

    @node_from(from_name='母盘-打开合成')
    @operation_node(name='母盘-识别界面')
    def hifi_check_ui(self) -> OperationRoundResult:
        """识别界面"""
        time.sleep(1)
        self.screenshot()

        result = self.round_by_find_area(self.last_screenshot, '音像店', '母盘合成')
        if result.is_success:
            return self.round_success(status='可合成')

        result = self.round_by_find_area(self.last_screenshot, '音像店', '文本-合成素材不足')
        if result.is_success:
            return self.round_success(status='素材不足')

        return self.round_retry(wait=1)

    @node_from(from_name='母盘-识别界面', status='可合成')
    @operation_node(name='母盘-执行合成')
    def hifi_perform_synthesis(self) -> OperationRoundResult:
        """执行合成"""
        result = self.round_by_find_and_click_area(self.last_screenshot, '音像店', '母盘合成')
        if result.is_success:
            return self.round_success(result.status, wait=1)
        return self.round_retry(wait=1)

    @node_from(from_name='母盘-执行合成')
    @operation_node(name='母盘-确认合成')
    def hifi_confirm(self) -> OperationRoundResult:
        """确认合成"""
        result = self.round_by_find_and_click_area(self.last_screenshot, '音像店', '确认')
        if result.is_success:
            return self.round_success(result.status, wait=1)
        return self.round_retry(wait=1)

    @node_from(from_name='母盘-确认合成')
    @node_from(from_name='母盘-识别界面', status='素材不足')
    @operation_node(name='母盘-返回大世界')
    def hifi_return(self) -> OperationRoundResult:
        """返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='母盘-返回大世界')
    @operation_node(name='母盘-完成')
    def hifi_complete(self) -> OperationRoundResult:
        """母盘合成完成，检查下一个任务"""
        self._task_results[self.TASK_HIFI_MASTER] = '完成'
        self._current_task_index += 1

        # 检查是否还有下一个任务
        if self._current_task_index < len(self._task_queue):
            next_task = self._task_queue[self._current_task_index]
            if next_task == self.TASK_ETHER_BATTERY:
                return self.round_success(status='执行电池合成')

        return self.round_success(status='全部完成')

    # ==================== 电池合成相关节点 ====================

    @node_from(from_name='检查配置', status='执行电池合成')
    @node_from(from_name='母盘-完成', status='执行电池合成')
    @operation_node(name='打开菜单')
    def goto_menu(self) -> OperationRoundResult:
        op = GotoMenu(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='打开菜单')
    @operation_node(name='电池-计算最大合成数量')
    def check_charge_power(self) -> OperationRoundResult:
        # 不能在快捷手册里面识别电量 因为每个人的备用电量不一样
        area = self.ctx.screen_loader.get_area('菜单', '文本-电量')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        digit = str_utils.get_positive_digits(ocr_result, None)
        if digit is None:
            return self.round_retry('未识别到电量', wait=1)

        self._max_source_ether_battery_synthetic_quantity = int(digit / 60)
        if self._max_source_ether_battery_synthetic_quantity < 1:
            return self.round_success(status="电量不足")
        return self.round_success(f'可以合成的电池数量为： {self._max_source_ether_battery_synthetic_quantity}个')

    @node_from(from_name='电池-计算最大合成数量')
    @operation_node(name='电池-前往合成')
    def battery_goto_synthesis(self) -> OperationRoundResult:
        """前往电池合成界面"""
        return self.round_by_goto_screen(screen_name='仓库-材料道具-道具处理')

    @node_from(from_name='电池-前往合成')
    @operation_node(name='电池-选择电池')
    def battery_select(self) -> OperationRoundResult:
        """选择电池"""
        result = self.round_by_find_area(self.last_screenshot, '仓库-材料道具-道具处理', '文本-以太电池')
        if result.is_success:
            time.sleep(0.5)
            if self.config.source_ether_battery_auto_synthetic_quantity == '两个':
                self.battery_select_number(1)
            elif self.config.source_ether_battery_auto_synthetic_quantity == '三个':
                self.battery_select_number(2)
            elif self.config.source_ether_battery_auto_synthetic_quantity == '四个':
                self.battery_select_number(3)
            elif self.config.source_ether_battery_auto_synthetic_quantity == '全部':
                self.battery_select_number(self._max_source_ether_battery_synthetic_quantity - 1)
            return self.round_success(status='可合成')

        result = self.round_by_find_area(self.last_screenshot, '仓库-材料道具-道具处理', '图像-以太电池')
        if result.is_success:
            time.sleep(0.5)
            return self.round_success(status='电量不足')

        return self.round_retry(wait=1)

    def battery_select_number(self, number: int) -> None:
        # 先找到目标区域
        area = self.ctx.screen_loader.get_area('仓库-材料道具-道具处理', '按钮-增加')
        if not area:
            return

        # 多次点击
        for i in range(number):
            self.ctx.controller.click(area.center)
            time.sleep(0.2)  # 每次点击间隔

    @node_from(from_name='电池-选择电池', status='可合成')
    @operation_node(name='电池-执行合成')
    def battery_perform(self) -> OperationRoundResult:
        """执行合成"""
        result = self.round_by_find_and_click_area(self.last_screenshot, '仓库-材料道具-道具处理', '按钮-合成')
        if result.is_success:
            time.sleep(0.5)
            return self.round_success(result.status)
        return self.round_retry(wait=1)

    @node_from(from_name='电池-执行合成')
    @operation_node(name='电池-确认合成')
    def battery_confirm(self) -> OperationRoundResult:
        """确认合成"""
        result = self.round_by_find_and_click_area(self.last_screenshot, '仓库-材料道具-道具处理', '按钮-确认')
        if result.is_success:
            time.sleep(0.5)
            return self.round_success(result.status)
        return self.round_retry(wait=1)

    @node_from(from_name='电池-选择电池', status='电量不足')
    @node_from(from_name='电池-确认合成')
    @operation_node(name='电池-完成')
    def battery_complete(self) -> OperationRoundResult:
        """电池合成完成"""
        self._task_results[self.TASK_ETHER_BATTERY] = '完成'
        self._current_task_index += 1

        # 检查是否还有下一个任务
        if self._current_task_index < len(self._task_queue):
            next_task = self._task_queue[self._current_task_index]
            if next_task == self.TASK_HIFI_MASTER:
                # 理论上电池合成后不会再有母盘合成，但为了完整性保留
                return self.round_success(status='执行母盘合成')

        return self.round_success(status='全部完成')

    # ==================== 最终返回节点 ====================

    @node_from(from_name='母盘-完成', status='全部完成')
    @node_from(from_name='电池-计算最大合成数量', status="电量不足")
    @node_from(from_name='电池-完成', status='全部完成')
    @node_from(from_name='检查配置', status='无需合成')
    @operation_node(name='最终返回')
    def final_return(self) -> OperationRoundResult:
        """最终返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug() -> None:
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = AutoSyntheticApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()