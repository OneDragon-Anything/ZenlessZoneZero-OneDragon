import time
import math
from typing import ClassVar, Optional

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

    STATUS_SUCCESS: ClassVar[str] = '电量恢复成功'
    STATUS_FAILED: ClassVar[str] = '电量恢复失败'
    STATUS_NO_NEED: ClassVar[str] = '无需恢复电量'
    STATUS_INSUFFICIENT: ClassVar[str] = '电量不足'

    # 电量来源类型常量
    SOURCE_BACKUP_CHARGE: ClassVar[str] = '储蓄电量'
    SOURCE_ETHER_BATTERY: ClassVar[str] = '以太电池'

    # 电量来源状态常量
    STATUS_USE_BACKUP_CHARGE: ClassVar[str] = f'使用{SOURCE_BACKUP_CHARGE}'
    STATUS_USE_ETHER_BATTERY: ClassVar[str] = f'使用{SOURCE_ETHER_BATTERY}'

    def __init__(self, ctx: ZContext, current_charge: int, required_charge: int,
                 restore_mode: str = RestoreChargeEnum.BOTH.value.value):
        """
        初始化电量恢复操作

        Args:
            ctx: ZContext实例
            current_charge: 当前电量
            required_charge: 需要的电量
            restore_mode: 恢复模式，参考RestoreChargeEnum
        """
        ZOperation.__init__(
            self,
            ctx=ctx,
            op_name='恢复电量'
        )
        self.current_charge = current_charge
        self.required_charge = required_charge
        self.restore_mode = restore_mode
        self.retry_count = 0
        self.max_retry_count = 3
        # 统一的状态管理
        self._current_source_type = None  # 当前选择的电量来源类型
        self._backup_charge_tried = False  # 是否已尝试过储蓄电量

    @operation_node(name='检查是否需要恢复电量', is_start_node=True)
    def check_need_restore(self) -> OperationRoundResult:
        """检查是否需要恢复电量"""
        if self.current_charge >= self.required_charge:
            return self.round_success(RestoreCharge.STATUS_NO_NEED)

        needed_power = self.required_charge - self.current_charge
        log.info(f'需要恢复电量: {needed_power} (当前: {self.current_charge}, 需要: {self.required_charge})')
        return self.round_success()

    @node_from(from_name='检查是否需要恢复电量')
    @node_from(from_name='电量恢复重试')
    @operation_node(name='点击电量文本')
    def click_charge_text(self) -> OperationRoundResult:
        """点击电量文本区域打开恢复界面"""
        area = self.ctx.screen_loader.get_area('菜单', '文本-电量')
        if area is None:
            return self.round_retry('未找到电量区域', wait=1)

        self.ctx.controller.click(area.center)
        return self.round_success('已点击电量文本')

    @node_from(from_name='点击电量文本')
    @operation_node(name='选择电量来源')
    def select_charge_source(self) -> OperationRoundResult:
        """根据配置和当前状态选择电量来源"""
        # 确定要使用的电量来源
        source_type = self._determine_charge_source()
        self._current_source_type = source_type

        if source_type == self.SOURCE_BACKUP_CHARGE:
            return self.round_success(self.STATUS_USE_BACKUP_CHARGE, wait=1)
        else:
            return self.round_success(self.STATUS_USE_ETHER_BATTERY, wait=1)

    def _determine_charge_source(self) -> str:
        """确定要使用的电量来源类型"""
        if self.restore_mode == RestoreChargeEnum.BACKUP_ONLY.value.value:
            return self.SOURCE_BACKUP_CHARGE
        elif self.restore_mode == RestoreChargeEnum.ETHER_ONLY.value.value:
            return self.SOURCE_ETHER_BATTERY
        else:
            # BOTH模式：如果还没尝试过储蓄电量，先尝试储蓄电量
            if not self._backup_charge_tried:
                return self.SOURCE_BACKUP_CHARGE
            else:
                return self.SOURCE_ETHER_BATTERY

    @node_from(from_name='选择电量来源', status=STATUS_USE_BACKUP_CHARGE)
    @node_from(from_name='选择电量来源', status=STATUS_USE_ETHER_BATTERY)
    @operation_node(name='选择并确认电量来源')
    def select_and_confirm_charge_source(self) -> OperationRoundResult:
        """选择并确认电量来源（储蓄电量或以太电池）"""
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
                self.restore_mode == RestoreChargeEnum.BOTH.value.value and
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
        needed_power = max(0, self.required_charge - self.current_charge)

        if needed_power <= 0:
            return self.round_success('计算出使用数量为0，无需恢复')

        if self._current_source_type == self.SOURCE_BACKUP_CHARGE:
            return self._handle_backup_charge(needed_power)
        else:
            return self._handle_ether_battery(needed_power)

    def _handle_backup_charge(self, needed_power: int) -> OperationRoundResult:
        """处理储蓄电量恢复"""
        # 获取当前储蓄电量数量
        saved_power_amount = self._get_backup_charge_amount()

        if saved_power_amount <= 0:
            # 储蓄电量不足，如果是BOTH模式则切换到以太电池
            if self.restore_mode == RestoreChargeEnum.BOTH.value.value:
                self._backup_charge_tried = True
                log.info(f'{self.SOURCE_BACKUP_CHARGE}已用完，切换{self.SOURCE_ETHER_BATTERY}')
                return self.round_retry('储蓄电量不足，切换电量来源')
            else:
                return self.round_fail(f'{self.SOURCE_BACKUP_CHARGE}不足')

        amount_to_use = min(needed_power, saved_power_amount)

        # 点击输入框并输入数量
        input_area = self.ctx.screen_loader.get_area('恢复电量', '兑换数量-数字区域')
        if input_area is None:
            return self.round_retry('未找到电量数量输入框', wait=1)

        self.ctx.controller.click(input_area.center)
        time.sleep(0.5)
        self.ctx.controller.input_str(str(amount_to_use))
        time.sleep(0.5)

        # 如果是BOTH模式且补完后电量还不够，标记需要切换到以太电池
        if self.restore_mode == RestoreChargeEnum.BOTH.value.value:
            after_charge = self.current_charge + amount_to_use
            if after_charge < self.required_charge:
                self._backup_charge_tried = True
                log.info(f'{self.SOURCE_BACKUP_CHARGE}不足，后续将切换{self.SOURCE_ETHER_BATTERY}')

        log.info(f"使用储蓄电量: {amount_to_use}")
        return self.round_success('储蓄电量设置完成')

    def _handle_ether_battery(self, needed_power: int) -> OperationRoundResult:
        """处理以太电池恢复"""
        # 每个电池恢复60体力
        battery_count = math.ceil(needed_power / 60)

        if battery_count <= 0:
            return self.round_success('计算出使用数量为0，无需恢复')

        # 获取加号位置
        plus_point: Point = Point(1274, 680)

        # 默认初始数量为1，所以只需点击battery_count-1次
        for _ in range(battery_count - 1):
            self.ctx.controller.click(plus_point)
            time.sleep(0.2)

        log.info(f"使用以太电池: {battery_count}个")
        return self.round_success('以太电池设置完成')

    def _get_backup_charge_amount(self) -> int:
        """获取当前储蓄电量数量"""
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)

        for ocr_result, mrl in ocr_result_map.items():
            if self.SOURCE_BACKUP_CHARGE in ocr_result:
                amount_str = str_utils.get_positive_digits(ocr_result, None)
                if amount_str is not None:
                    try:
                        return int(amount_str)
                    except ValueError:
                        log.warning(f"无法解析储蓄电量数值: {amount_str}")
                        return 0
                break

        log.warning("未找到储蓄电量信息")
        return 0

    @node_from(from_name='设置使用数量')
    @operation_node(name='确认恢复电量')
    def confirm_restore_charge(self) -> OperationRoundResult:
        """确认恢复电量"""
        confirm_area = self.ctx.screen_loader.get_area('恢复电量', '兑换确认')

        if confirm_area is None:
            # 通过OCR识别确认按钮
            ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
            for ocr_result, mrl in ocr_result_map.items():
                if '确认' in ocr_result or '确定' in ocr_result:
                    if mrl.max is not None:
                        self.ctx.controller.click(mrl.max.center)
                        break
            else:
                return self.round_retry('未找到确认按钮', wait=1)
        else:
            self.ctx.controller.click(confirm_area.center)

        time.sleep(2)
        return self.round_success('电量恢复完成')

    @node_from(from_name='确认恢复电量')
    @operation_node(name='检查恢复后电量')
    def check_charge_after_restore(self) -> OperationRoundResult:
        """检查恢复后的电量是否足够"""
        time.sleep(2)

        # 重新打开菜单并检查电量
        op = GotoMenu(self.ctx)
        result = op.execute()
        if not result.success:
            return self.round_by_op_result(result)

        # 通过OCR识别当前电量
        area = self.ctx.screen_loader.get_area('菜单', '文本-电量')
        if area is None:
            return self.round_retry('未找到电量显示区域', wait=1)

        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        current_charge_str = str_utils.get_positive_digits(ocr_result, None)

        if current_charge_str is None:
            return self.round_retry('未识别到电量数值', wait=1)

        # 更新当前电量，确保类型为int
        try:
            current_charge = int(current_charge_str)
            self.current_charge = current_charge
        except ValueError:
            return self.round_retry(f'电量数值格式错误: {current_charge_str}', wait=1)

        # 检查电量是否足够
        if self.current_charge >= self.required_charge:
            return self.round_success(f'电量恢复成功！当前电量: {current_charge}, 需要电量: {self.required_charge}')
        else:
            shortage = self.required_charge - self.current_charge
            return self.round_fail(f'电量仍不足！当前电量: {current_charge}, 需要电量: {self.required_charge}, 缺少: {shortage}')

    @node_from(from_name='检查恢复后电量', success=False)
    @operation_node(name='电量恢复重试')
    def retry_restore_charge(self) -> OperationRoundResult:
        """电量恢复重试逻辑"""
        self.retry_count += 1

        if self.retry_count < self.max_retry_count:
            log.info(f'电量仍不足，尝试第{self.retry_count + 1}次恢复')
            # 重置状态，重新开始恢复流程
            self._reset_state_for_retry()
            return self.round_success('电量仍不足，尝试再次恢复')
        else:
            log.info('已达到最大重试次数，电量恢复失败')
            return self.round_fail('已达到最大重试次数，电量恢复失败')

    def _reset_state_for_retry(self):
        """重置状态用于重试"""
        # 如果之前尝试过储蓄电量但还不够，下次重试时直接使用以太电池
        if (self._backup_charge_tried and
            self.restore_mode == RestoreChargeEnum.BOTH.value.value):
            # 保持已尝试储蓄电量的状态，下次会直接用以太电池
            pass
        else:
            # 重置为初始状态
            self._current_source_type = None
            self._backup_charge_tried = False

    @node_from(from_name='检查恢复后电量', success=True)
    @operation_node(name='恢复电量成功')
    def restore_charge_success(self) -> OperationRoundResult:
        """电量恢复成功"""
        return self.round_success(RestoreCharge.STATUS_SUCCESS)

    @node_from(from_name='点击电量文本', success=False)
    @node_from(from_name='选择并确认电量来源', success=False)
    @node_from(from_name='设置使用数量', success=False)
    @node_from(from_name='确认恢复电量', success=False)
    @node_from(from_name='电量恢复重试', success=False)
    @node_from(from_name='重新选择电量来源', success=False)
    @operation_node(name='恢复电量失败')
    def restore_charge_failed(self) -> OperationRoundResult:
        """电量恢复失败"""
        log.error('电量恢复失败')
        return self.round_fail(RestoreCharge.STATUS_FAILED)

    @node_from(from_name='检查是否需要恢复电量', status=STATUS_NO_NEED)
    @operation_node(name='无需恢复电量')
    def no_need_restore(self) -> OperationRoundResult:
        """无需恢复电量"""
        return self.round_success(RestoreCharge.STATUS_NO_NEED)
