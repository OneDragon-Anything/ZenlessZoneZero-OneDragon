from typing import ClassVar

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
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
    负责处理菜单态和副本内的恢复电量弹窗，支持储蓄电量和以太电池两种恢复方式
    菜单态只预读来源数量并判断是否值得进本，真正的恢复数量确认留到副本内执行
    """

    SOURCE_BACKUP_CHARGE: ClassVar[str] = '储蓄电量'
    SOURCE_ETHER_BATTERY: ClassVar[str] = '以太电池'
    STATUS_CHARGE_NOT_ENOUGH: ClassVar[str] = '电量不足'
    STATUS_RESTORE_SUCCESS: ClassVar[str] = '恢复电量成功'

    def __init__(self, ctx: ZContext, required_charge: int | None = None, is_menu: bool = False) -> None:
        """
        初始化电量恢复操作

        Args:
            ctx: ZContext实例
            required_charge: 菜单态预读时所需的电量
            is_menu: 是否在菜单界面
        """
        ZOperation.__init__(
            self,
            ctx=ctx,
            op_name='恢复电量'
        )
        self.config: ChargePlanConfig = self.ctx.run_context.get_config(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.required_charge = required_charge
        self.is_menu = is_menu
        self.is_after_battle_retry: bool = False
        self.skip_backup_charge: bool = False

    def _should_probe_source_in_menu(self) -> bool:
        return self.is_menu and self.required_charge is not None

    def _should_confirm_restore(self, current_amount: int, exchange_amount: int) -> bool:
        if exchange_amount > current_amount:
            return False
        return exchange_amount < current_amount

    def _is_source_charge_enough(self, source: str, current_amount: int) -> bool:
        if self.required_charge is None:
            return True
        if source == self.SOURCE_BACKUP_CHARGE:
            return current_amount >= self.required_charge
        if source == self.SOURCE_ETHER_BATTERY:
            return current_amount * 60 >= self.required_charge
        return True

    def _should_reselect_source(self, source: str) -> bool:
        return (
            source == self.SOURCE_BACKUP_CHARGE
            and self.config.restore_charge == RestoreChargeEnum.BOTH.value.value
        )

    def _get_amount_by_area(self, area_name: str) -> int | None:
        amount_area = self.ctx.screen_loader.get_area('恢复电量', area_name)
        part = cv2_utils.crop_image_only(self.last_screenshot, amount_area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        return str_utils.get_positive_digits(ocr_result)

    @node_from(from_name='关闭快捷使用', status='重新选择电量来源')
    @operation_node(name='打开恢复界面', is_start_node=True)
    def click_charge_text(self) -> OperationRoundResult:
        # 检查是否已经在恢复界面
        result = self.round_by_find_area(self.last_screenshot, '恢复电量', '标题-恢复电量')
        if result.is_success:
            return self.round_success()

        if self.is_menu:
            return self.round_by_find_and_click_area(self.last_screenshot, '菜单', '文本-电量', success_wait=0.5)
        if self.is_after_battle_retry:
            return self.round_by_find_and_click_area(self.last_screenshot, '战斗画面', '战斗结果-再来一次', success_wait=0.5)
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
            if self.skip_backup_charge:
                target_list = target_list[1:]
        else:
            target_list = []

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
        click = self.round_by_find_and_click_area(self.last_screenshot, '恢复电量', '确认', success_wait=0.5, retry_wait=0.5)
        if click.is_success:
            return self.round_success(status=self.previous_node.status, wait=0.5)
        return self.round_retry('未找到确认按钮', wait=0.5)

    @node_from(from_name='确认电量来源')
    @operation_node(name='识别当前数量')
    def set_charge_amount(self) -> OperationRoundResult:
        source = self.previous_node.status
        if source is None:
            return self.round_retry('未识别到电量来源', wait=0.5)

        if self._should_probe_source_in_menu():
            quick_use_result = self.round_by_find_area(self.last_screenshot, '恢复电量', '标题-快捷使用')
            if not quick_use_result.is_success:
                return self.round_retry('未识别到快捷使用', wait=0.5)

        current_amount = self._get_amount_by_area('当前数量')
        if current_amount is None:
            return self.round_retry('未识别到当前数量', wait=0.5)

        log.info(f'{source} {current_amount}')

        if self._should_probe_source_in_menu():
            # 菜单态这里只预读可用恢复量，真正的提取留到副本里点“下一步”后再确认
            # 储蓄电量和以太电池都会先进入“快捷使用”，再读取对应来源的当前数量
            if self._is_source_charge_enough(source, current_amount):
                return self.round_success(status='继续前往副本', data=current_amount, wait=0.5)
            if self._should_reselect_source(source):
                self.skip_backup_charge = True
                return self.round_success(status='重新选择电量来源', data=current_amount, wait=0.5)
            return self.round_success(status=self.STATUS_CHARGE_NOT_ENOUGH, data=current_amount, wait=0.5)

        exchange_amount = self._get_amount_by_area('兑换数量-数字输入框')
        if exchange_amount is None:
            return self.round_retry('未识别到兑换数量', wait=0.5)

        log.info(f'{source} 兑换数量 {exchange_amount}')
        if exchange_amount > current_amount:
            return self.round_retry('兑换数量大于当前数量', wait=0.5)

        if not self._should_confirm_restore(current_amount, exchange_amount):
            if self._should_reselect_source(source):
                self.skip_backup_charge = True
                return self.round_success(status='重新选择电量来源', data=exchange_amount, wait=0.5)
            return self.round_success(status=self.STATUS_CHARGE_NOT_ENOUGH, data=exchange_amount, wait=0.5)

        return self.round_success(status=source, data=exchange_amount, wait=0.5)

    @node_from(from_name='识别当前数量', status='继续前往副本')
    @node_from(from_name='识别当前数量', status='重新选择电量来源')
    @node_from(from_name='识别当前数量', status=STATUS_CHARGE_NOT_ENOUGH)
    @operation_node(name='关闭快捷使用')
    def close_quick_use_popup(self) -> OperationRoundResult:
        # 菜单态预读后，关闭“快捷使用”就会直接回到菜单，不需要再额外关闭一次外层“恢复电量”弹窗
        result = self.round_by_find_area(self.last_screenshot, '恢复电量', '标题-快捷使用')
        if not result.is_success:
            return self.round_success(status=self.previous_node.status, wait=0.5)

        result = self.round_by_find_and_click_area(self.last_screenshot, '菜单', '关闭', success_wait=0.5, retry_wait=0.5)
        if result.is_success:
            return self.round_retry('尝试关闭快捷使用', wait=0.5)

        return self.round_retry('未关闭快捷使用', wait=0.5)

    @node_from(from_name='识别当前数量', status=SOURCE_BACKUP_CHARGE)
    @node_from(from_name='识别当前数量', status=SOURCE_ETHER_BATTERY)
    @operation_node(name='确认恢复电量')
    def confirm_restore_charge(self) -> OperationRoundResult:
        # 菜单态预读后，不会走到这里；这里只有副本内真正恢复时才点确认
        return self.round_by_find_and_click_area(self.last_screenshot, '恢复电量', '确认', success_wait=1, retry_wait=0.5)

    @node_from(from_name='确认恢复电量')
    @operation_node(name='恢复后处理')
    def confirm_after_restore(self) -> OperationRoundResult:
        """
        选副本阶段触发恢复：“恢复电量”的确认->“快捷使用”的确认->“获得”的确认
        战斗后点“再来一次”触发恢复：“恢复电量”的确认->“快捷使用”的确认
        上个节点已处理“快捷使用”的确认，这个节点处理后续可能出现的确认层
        """
        for area_name in ('标题-获得', '标题-快捷使用'):
            result = self.round_by_find_area(self.last_screenshot, '恢复电量', area_name)
            if not result.is_success:
                continue
            result = self.round_by_find_and_click_area(self.last_screenshot, '恢复电量', '确认', success_wait=0.5, retry_wait=0.5)
            if result.is_success:
                return self.round_wait('等待恢复完成', wait=0.5)
            return self.round_retry('恢复电量失败', wait=0.5)

        return self.round_success(self.STATUS_RESTORE_SUCCESS, wait=0.5)

def __debug_charge():
    ctx = ZContext()
    ctx.init()
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
    ctx.init()
    ctx.init_ocr()
    ctx.run_context.start_running()
    op = RestoreCharge(ctx, required_charge=10)
    op.execute()

if __name__ == '__main__':
    __debug()
