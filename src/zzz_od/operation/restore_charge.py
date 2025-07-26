import time
from typing import ClassVar

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.log_utils import log
from one_dragon.base.geometry.point import Point
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem, RestoreChargeEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.operation.goto.goto_menu import GotoMenu


class RestoreCharge(ZOperation):
    """
    电量恢复操作类
    负责在菜单界面恢复电量，支持储蓄电量和以太电池两种恢复方式
    """

    SOURCE_BACKUP_CHARGE: ClassVar[str] = '储蓄电量'
    SOURCE_ETHER_BATTERY: ClassVar[str] = '以太电池'

    def __init__(self, ctx: ZContext, required_charge: int, is_menu = False):
        """
        初始化电量恢复操作

        Args:
            ctx: ZContext实例
            required_charge: 需要的电量
            is_menu: 是否在菜单界面
        """
        ZOperation.__init__(
            self,
            ctx=ctx,
            op_name='恢复电量'
        )
        self.required_charge = required_charge
        self.is_menu = is_menu

        self._current_source_type = None  # 当前选择的电量来源类型
        self._backup_charge_tried = False  # 是否已尝试过储蓄电量

    @operation_node(name='打开恢复界面')
    def click_charge_text(self) -> OperationRoundResult:
        """点击电量文本区域或者下一步打开恢复界面"""
        # 检查是否已经在恢复界面
        result = self.round_by_find_area(self.last_screenshot, '实战模拟室', '恢复电量')
        if result.is_success:
            return self.round_success()

        if self.is_menu:
            return self.round_by_find_and_click_area('菜单', '文本-电量')
        else:
            return self.round_by_find_and_click_area(self.last_screenshot, '实战模拟室', '下一步')

    @node_from(from_name='打开恢复界面')
    @operation_node(name='选择电量来源')
    def select_charge_source(self) -> OperationRoundResult:
        """根据配置和当前状态选择电量来源"""
        if self.ctx.charge_plan_config.restore_charge == RestoreChargeEnum.BACKUP_ONLY.value.value:
            self._current_source_type = self.SOURCE_BACKUP_CHARGE
        elif self.ctx.charge_plan_config.restore_charge == RestoreChargeEnum.ETHER_ONLY.value.value:
            self._current_source_type = self.SOURCE_ETHER_BATTERY
        else:
            # BOTH模式：如果还没尝试过储蓄电量，先尝试储蓄电量
            if not self._backup_charge_tried:
                self._current_source_type = self.SOURCE_BACKUP_CHARGE
            else:
                self._current_source_type = self.SOURCE_ETHER_BATTERY

        if self._current_source_type == self.SOURCE_BACKUP_CHARGE:
            return self.round_success(self.SOURCE_BACKUP_CHARGE, wait=1)
        else:
            return self.round_success(self.SOURCE_ETHER_BATTERY, wait=1)

    @node_from(from_name='选择电量来源', status=SOURCE_BACKUP_CHARGE)
    @node_from(from_name='选择电量来源', status=SOURCE_ETHER_BATTERY)
    @operation_node(name='选择并确认电量来源')
    def select_and_confirm_charge_source(self) -> OperationRoundResult:
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)

        target_text = self._current_source_type
        found_source = False

        for ocr_result, mrl in ocr_result_map.items():
            if target_text in ocr_result:
                if mrl.max is not None:
                    click_point = mrl.max.center
                    # 向上移动100个像素点击选择框
                    offset_point = Point(click_point.x, click_point.y - 100)
                    self.ctx.controller.click(offset_point)
                    found_source = True
                    break

        if not found_source:
            # 如果是储蓄电量找不到且是BOTH模式，尝试切换到以太电池
            if (target_text == self.SOURCE_BACKUP_CHARGE and
                self.ctx.charge_plan_config.restore_charge == RestoreChargeEnum.BOTH.value.value and
                not self._backup_charge_tried):
                self._backup_charge_tried = True
                log.info(f'{self.SOURCE_BACKUP_CHARGE}不可用，切换{self.SOURCE_ETHER_BATTERY}')
                # 重新选择电量来源
                return self.round_retry('切换电量来源', wait=0.5)
            return self.round_retry(f'未找到{target_text}文本', wait=1)

        time.sleep(0.5)

        # 点击选择来源的确认按钮
        confirm_area = self.ctx.screen_loader.get_area('恢复电量', '选择来源-确认')
        if confirm_area is not None:
            self.ctx.controller.click(confirm_area.center)

        return self.round_success(self._current_source_type)

    @node_from(from_name='选择并确认电量来源', success=False)
    @operation_node(name='重新选择电量来源')
    def reselect_charge_source(self) -> OperationRoundResult:
        """重新选择电量来源（用于BOTH模式的切换）"""
        return self.select_charge_source()

    @node_from(from_name='重新选择电量来源')
    @node_from(from_name='选择并确认电量来源', status=SOURCE_BACKUP_CHARGE)
    @node_from(from_name='选择并确认电量来源', status=SOURCE_ETHER_BATTERY)
    @operation_node(name='设置使用数量')
    def set_charge_amount(self) -> OperationRoundResult:
        """设置恢复电量的数量"""
        if not self.is_menu:
            return self.round_success(wait=0.5)

        amount_area = self.ctx.screen_loader.get_area('恢复电量', '当前数量')
        part = cv2_utils.crop_image_only(self.last_screenshot, amount_area.rect)

        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        current_amount = str_utils.get_positive_digits(ocr_result)
        if current_amount is None:
            return self.round_retry('未识别到电量数值', wait=0.5)

        if self._current_source_type == self.SOURCE_BACKUP_CHARGE:
            return self.handle_backup_charge(current_amount)
        else:
            return self.handle_ether_battery(current_amount)

    def handle_backup_charge(self, available_backup_charge: int) -> OperationRoundResult:
        """处理储蓄电量恢复"""
        # 获取当前储蓄电量数量

        if available_backup_charge is None:
            return self.round_retry('未识别到电量数值', wait=1)

        if available_backup_charge <= 0:
            # 储蓄电量不足，如果是BOTH模式则切换到以太电池
            if self.ctx.charge_plan_config.restore_charge == RestoreChargeEnum.BOTH.value.value:
                self._backup_charge_tried = True
                log.info(f'{self.SOURCE_BACKUP_CHARGE}已用完，切换{self.SOURCE_ETHER_BATTERY}')
                return self.round_retry('储蓄电量不足，切换电量来源')
            else:
                return self.round_fail(f'{self.SOURCE_BACKUP_CHARGE}不足')

        amount_to_use = min(self.required_charge, available_backup_charge)

        # 点击输入框并输入数量
        input_area = self.ctx.screen_loader.get_area('恢复电量', '兑换数量-数字区域')
        if input_area is None:
            return self.round_retry('未找到电量数量输入框', wait=1)

        self.ctx.controller.click(input_area.center)
        time.sleep(0.5)
        self.ctx.controller.input_str(str(amount_to_use))
        time.sleep(0.5)

        # 如果是BOTH模式且补完后电量还不够，标记需要切换到以太电池
        if self.ctx.charge_plan_config.restore_charge == RestoreChargeEnum.BOTH.value.value:
            after_charge = self.required_charge - amount_to_use
            if after_charge < self.required_charge:
                self._backup_charge_tried = True
                log.info(f'{self.SOURCE_BACKUP_CHARGE}不足，后续将切换{self.SOURCE_ETHER_BATTERY}')

        log.info(f"使用储蓄电量: {amount_to_use}")
        return self.round_success(wait=0.5)

    def handle_ether_battery(self, available_battery_count: int) -> OperationRoundResult:
        """处理以太电池恢复"""
        # 每个电池恢复60体力
        need_battery_count = (self.required_charge + 59) // 60
        usable_battery_count = min(need_battery_count, available_battery_count)

        # 获取加号位置
        plus_point: Point = Point(1274, 680)

        # 默认初始数量为1，所以只需点击battery_count-1次
        for _ in range(usable_battery_count - 1):
            self.ctx.controller.click(plus_point)
            time.sleep(0.2)

        log.info(f"使用以太电池: {usable_battery_count}个")
        return self.round_success(wait=0.5)

    @node_from(from_name='设置使用数量')
    @operation_node(name='确认恢复电量')
    def confirm_restore_charge(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(self.last_screenshot, '恢复电量', '兑换确认')
        if result.is_success:
            return self.round_success(result.status, wait=0.5)

        return self.round_retry(result.status, wait=1)


def __debug_charge():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.start_running()
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('_1753519599239')
    amount_area = ctx.screen_loader.get_area('恢复电量', '当前数量')
    part = cv2_utils.crop_image_only(screen, amount_area.rect)
    ocr_result = ctx.ocr.run_ocr_single_line(part)
    current_amount = str_utils.get_positive_digits(ocr_result, 0)
    print(f'当前数量识别结果: {current_amount}')
    cv2_utils.show_image(part, wait=0)
    print(ocr_result)

def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.start_running()
    op = RestoreCharge(ctx, required_charge=10)
    op.execute()

if __name__ == '__main__':
    __debug()
