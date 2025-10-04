import time
from typing import ClassVar, Optional

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    RestoreChargeEnum,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class RestoreCharge(ZOperation):
    """
    电量恢复操作类
    负责在菜单界面恢复电量，支持储蓄电量和以太电池两种恢复方式
    """

    SOURCE_BACKUP_CHARGE: ClassVar[str] = '储蓄电量'
    SOURCE_ETHER_BATTERY: ClassVar[str] = '以太电池'

    def __init__(self, ctx: ZContext, required_charge: int | None = None, is_menu: bool = False):
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
        self.config: Optional[ChargePlanConfig] = self.ctx.run_context.get_config(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.required_charge = required_charge
        self.is_menu = is_menu

    @operation_node(name='打开恢复界面', is_start_node=True)
    def click_charge_text(self) -> OperationRoundResult:
        # 检查是否已经在恢复界面
        result = self.round_by_find_area(self.last_screenshot, '实战模拟室', '恢复电量')
        if result.is_success:
            return self.round_success()

        if self.is_menu:
            return self.round_by_find_and_click_area(self.last_screenshot, '菜单', '文本-电量', success_wait=0.5)
        else:
            return self.round_by_find_and_click_area(self.last_screenshot, '实战模拟室', '下一步', success_wait=0.5)

    @node_from(from_name='打开恢复界面')
    @operation_node(name='选择电量来源')
    def select_charge_source(self) -> OperationRoundResult:
        if self.config.restore_charge == RestoreChargeEnum.BACKUP_ONLY.value.value:
            target_list = [self.SOURCE_BACKUP_CHARGE]
        elif self.config.restore_charge == RestoreChargeEnum.ETHER_ONLY.value.value:
            target_list = [self.SOURCE_ETHER_BATTERY]
        elif self.config.restore_charge == RestoreChargeEnum.BOTH.value.value:
            target_list = [self.SOURCE_BACKUP_CHARGE, self.SOURCE_ETHER_BATTERY]

        target_text_list = [gt(text, 'game') for text in target_list]
        target_area = self.ctx.screen_loader.get_area('恢复电量', '类型')

        return self.round_by_ocr_and_click_by_priority(
            screen=self.last_screenshot,
            target_cn_list=target_text_list,
            area=target_area,
            offset=Point(0, -100)
        )

    @node_from(from_name='选择电量来源')
    @operation_node(name='确认电量来源')
    def confirm_charge_source(self) -> OperationRoundResult:
        confirm_area = self.ctx.screen_loader.get_area('恢复电量', '确认')
        click = self.round_by_ocr_and_click(self.last_screenshot, gt('确认', 'game'), confirm_area)
        if click.is_success:
            return self.round_success(status=self.previous_node.status, wait=0.5)

    @node_from(from_name='确认电量来源')
    @operation_node(name='识别当前数量')
    def set_charge_amount(self) -> OperationRoundResult:
        if not self.is_menu:
            return self.round_success(wait=0.5)

        current_amount = None

        amount_area = self.ctx.screen_loader.get_area('恢复电量', '当前数量')
        part = cv2_utils.crop_image_only(self.last_screenshot, amount_area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        current_amount = str_utils.get_positive_digits(ocr_result)

        if current_amount is None:
            return self.round_retry('未识别到电量数值', wait=0.5)
        else:
            return self.round_success(status=self.previous_node.status, data=current_amount, wait=0.5)

    @node_from(from_name='识别当前数量', status=SOURCE_BACKUP_CHARGE)
    @operation_node(name='处理储蓄电量恢复')
    def handle_backup_charge(self) -> OperationRoundResult:
        if self.required_charge is None:
            return self.round_success()

        # 点击输入框并输入数量
        amount_to_use = min(self.required_charge, self.previous_node.data)
        input_area = self.ctx.screen_loader.get_area('恢复电量', '兑换数量-数字输入框')
        self.ctx.controller.click(input_area.center)
        time.sleep(0.5)
        self.ctx.controller.input_str(str(amount_to_use))

        return self.round_success(wait=0.5)

    @node_from(from_name='识别当前数量', status=SOURCE_ETHER_BATTERY)
    @operation_node(name='处理以太电池恢复')
    def handle_ether_battery(self) -> OperationRoundResult:
        if self.required_charge is None:
            return self.round_success()

        # 每个电池恢复60体力
        need_battery_count = (self.required_charge + 59) // 60
        usable_battery_count = min(need_battery_count, self.previous_node.data)

        # 获取加号位置
        plus_point = self.ctx.screen_loader.get_area('恢复电量', '兑换数量-加').center

        # 默认初始数量为1，所以只需点击battery_count-1次
        for _ in range(usable_battery_count - 1):
            self.ctx.controller.click(plus_point)
            time.sleep(0.2)

        return self.round_success(wait=0.5)

    @node_from(from_name='处理储蓄电量恢复')
    @node_from(from_name='处理以太电池恢复')
    @node_from(from_name='识别当前数量')
    @operation_node(name='确认恢复电量')
    def confirm_restore_charge(self) -> OperationRoundResult:
        confirm_area = self.ctx.screen_loader.get_area('恢复电量', '确认')
        return self.round_by_ocr_and_click(self.last_screenshot, gt('确认', 'game'), confirm_area, success_wait=1)

    @node_from(from_name='确认恢复电量')
    @operation_node(name='恢复后点击确认')
    def confirm_after_restore(self) -> OperationRoundResult:
        confirm_area = self.ctx.screen_loader.get_area('恢复电量', '确认')
        result = self.round_by_ocr_and_click(self.last_screenshot, gt('确认', 'game'), confirm_area, success_wait=0.5)
        if result.is_success:
            return self.round_success('恢复电量成功', wait=0.5)
        else:
            return self.round_retry('恢复电量失败', wait=0.5)


def __debug_charge():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
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
    ctx.run_context.start_running()
    op = RestoreCharge(ctx, required_charge=10)
    op.execute()

if __name__ == '__main__':
    __debug()
