from typing import ClassVar, Optional

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.zzz_application import ZApplication
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem, CardNumEnum, AutoRecoverChargeEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.compendium.combat_simulation import CombatSimulation
from zzz_od.operation.compendium.expert_challenge import ExpertChallenge
from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt
from zzz_od.operation.compendium.routine_cleanup import RoutineCleanup
from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium
from zzz_od.operation.goto.goto_menu import GotoMenu


class ChargePlanApp(ZApplication):

    STATUS_NO_PLAN: ClassVar[str] = '没有可运行的计划'
    STATUS_ROUND_FINISHED: ClassVar[str] = '已完成一轮计划'
    STATUS_TRY_RECOVER_CHARGE: ClassVar[str] = '尝试回复电量'

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='charge_plan',
            op_name=gt('体力刷本'),
            run_record=ctx.charge_plan_run_record,
            need_notify=True,
        )
        self.charge_power: int = 0  # 剩余电量
        self.need_to_check_power_in_mission: bool = False
        self.next_can_run_times: int = 0
        self.last_tried_plan: Optional[ChargePlanItem] = None
        self.next_plan: Optional[ChargePlanItem] = None
        self.ctx.charge_plan_config.reset_plans()

    @operation_node(name='开始体力计划', is_start_node=True)
    def start_charge_plan(self) -> OperationRoundResult:
        self.last_tried_plan = None
        return self.round_success()

    @node_from(from_name='挑战成功')
    @node_from(from_name='挑战失败')
    @node_from(from_name='开始体力计划')
    @node_from(from_name='电量不足')
    @node_from(from_name='电量回复失败')
    @node_from(from_name='回复电量后重新打开菜单')
    @operation_node(name='打开菜单')
    def goto_menu(self) -> OperationRoundResult:
        op = GotoMenu(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='打开菜单')
    @operation_node(name='识别电量')
    def check_charge_power(self) -> OperationRoundResult:
        screen = self.screenshot()
        # 不能在快捷手册里面识别电量 因为每个人的备用电量不一样
        area = self.ctx.screen_loader.get_area('菜单', '文本-电量')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        digit = str_utils.get_positive_digits(ocr_result, None)
        if digit is None:
            return self.round_retry('未识别到电量', wait=1)

        self.charge_power = digit
        return self.round_success(f'剩余电量 {digit}')

    @node_from(from_name='识别电量')
    @operation_node(name='检查电量是否足够')
    def check_charge_sufficiency(self) -> OperationRoundResult:
        """
        检查当前电量是否足够执行任何计划
        如果电量不足且开启了自动回复，则尝试回复电量
        """
        # 检查是否所有计划都已完成
        if self.ctx.charge_plan_config.all_plan_finished():
            return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)
        
        # 计算所需的最小电量
        min_required_power = float('inf')
        for plan in self.ctx.charge_plan_config.plan_list:
            if plan.run_times >= plan.plan_times:
                continue  # 跳过已完成的计划
                
            if plan.category_name == '实战模拟室':
                if plan.card_num != CardNumEnum.DEFAULT.value.value:
                    required = int(plan.card_num) * 20
                else:
                    required = 20  # 默认至少需要20
            elif plan.category_name == '定期清剿':
                required = 60
            elif plan.category_name == '专业挑战室':
                required = 40
            elif plan.category_name == '恶名狩猎':
                required = 60
            else:
                required = 20  # 默认值
            
            min_required_power = min(min_required_power, required)
        
        # 如果电量不足且开启了自动回复
        if self.charge_power < min_required_power and self.ctx.charge_plan_config.auto_recover_charge != AutoRecoverChargeEnum.NONE.value.value:
            return self.round_success(ChargePlanApp.STATUS_TRY_RECOVER_CHARGE)
        
        # 电量足够，继续正常流程
        return self.round_success()

    @node_from(from_name='检查电量是否足够')
    @operation_node(name='查找并选择下一个可执行任务')
    def find_and_select_next_plan(self) -> OperationRoundResult:
        """
        查找计划列表中的下一个可执行任务（未完成且体力足够）。
        如果找到，更新 self.next_plan 并返回成功状态。
        如果找不到，返回计划完成状态。
        """
        # 检查是否所有计划都已完成
        if self.ctx.charge_plan_config.all_plan_finished():
            # 如果开启了循环模式且所有计划已完成，重置计划并继续
            if self.ctx.charge_plan_config.loop:
                self.last_tried_plan = None
                self.ctx.charge_plan_config.reset_plans()
            else:
                return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)

        # 使用循环而不是递归来查找下一个可执行的任务
        while True:
            # 查找下一个未完成的计划
            candidate_plan = self.ctx.charge_plan_config.get_next_plan(self.last_tried_plan)
            if candidate_plan is None:
                return self.round_fail(ChargePlanApp.STATUS_NO_PLAN)

            # 计算所需电量
            need_charge_power = 1000  # 默认值，确保在未知情况下会检查
            self.need_to_check_power_in_mission = False

            if candidate_plan.category_name == '实战模拟室' and candidate_plan.card_num == CardNumEnum.DEFAULT.value.value:
                self.need_to_check_power_in_mission = True
            elif candidate_plan.category_name == '定期清剿' and self.ctx.charge_plan_config.use_coupon:
                self.need_to_check_power_in_mission = True
            else:
                if candidate_plan.category_name == '实战模拟室':
                    need_charge_power = int(candidate_plan.card_num) * 20
                elif candidate_plan.category_name == '定期清剿':
                    need_charge_power = 60
                elif candidate_plan.category_name == '专业挑战室':
                    need_charge_power = 40
                elif candidate_plan.category_name == '恶名狩猎':
                    need_charge_power = 60
                else:
                    self.need_to_check_power_in_mission = True

            # 检查电量是否足够
            if not self.need_to_check_power_in_mission and self.charge_power < need_charge_power:
                # 如果开启了自动回复电量，允许继续执行以触发回复流程
                if self.ctx.charge_plan_config.auto_recover_charge != AutoRecoverChargeEnum.NONE.value.value:
                    # 设置下一个计划并继续，让传送阶段处理电量不足
                    self.next_plan = candidate_plan
                    return self.round_success()
                # 如果没有开启自动回复，执行原来的逻辑
                elif not self.ctx.charge_plan_config.skip_plan:
                    return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)
                else:
                    # 跳过当前计划，继续查找下一个任务
                    self.last_tried_plan = candidate_plan
                    continue

            # 计算可运行次数
            self.next_can_run_times = 0
            if not self.need_to_check_power_in_mission:
                self.next_can_run_times = self.charge_power // need_charge_power
                max_need_run_times = candidate_plan.plan_times - candidate_plan.run_times
                if self.next_can_run_times > max_need_run_times:
                    self.next_can_run_times = max_need_run_times

            # 设置下一个计划并返回成功
            self.next_plan = candidate_plan
            return self.round_success()

    @node_from(from_name='查找并选择下一个可执行任务')
    @operation_node(name='传送')
    def transport(self) -> OperationRoundResult:
        # 如果开启了自动回复电量，在传送前再次检查电量
        if self.ctx.charge_plan_config.auto_recover_charge != AutoRecoverChargeEnum.NONE.value.value:
            # 计算所需电量
            need_charge_power = 1000
            if self.next_plan.category_name == '实战模拟室':
                if self.next_plan.card_num != CardNumEnum.DEFAULT.value.value:
                    need_charge_power = int(self.next_plan.card_num) * 20
            elif self.next_plan.category_name == '定期清剿':
                need_charge_power = 60
            elif self.next_plan.category_name == '专业挑战室':
                need_charge_power = 40
            elif self.next_plan.category_name == '恶名狩猎':
                need_charge_power = 60
            
            # 如果电量不足，触发电量不足节点
            if need_charge_power != 1000 and self.charge_power < need_charge_power:
                return self.round_fail('电量不足，需要回复')
        
        # 使用已经在查找并选择下一个可执行任务节点中设置好的self.next_plan
        op = TransportByCompendium(self.ctx,
                                   self.next_plan.tab_name,
                                   self.next_plan.category_name,
                                   self.next_plan.mission_type_name)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='识别副本分类')
    def check_mission_type(self) -> OperationRoundResult:
        return self.round_success(self.next_plan.category_name)

    @node_from(from_name='识别副本分类', status='实战模拟室')
    @operation_node(name='实战模拟室')
    def combat_simulation(self) -> OperationRoundResult:
        op = CombatSimulation(self.ctx, self.next_plan,
                              need_check_power=self.need_to_check_power_in_mission,
                              can_run_times=None if self.need_to_check_power_in_mission else self.next_can_run_times)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别副本分类', status='定期清剿')
    @operation_node(name='定期清剿')
    def routine_cleanup(self) -> OperationRoundResult:
        op = RoutineCleanup(self.ctx, self.next_plan,
                            need_check_power=self.need_to_check_power_in_mission,
                            can_run_times=None if self.need_to_check_power_in_mission else self.next_can_run_times)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别副本分类', status='专业挑战室')
    @operation_node(name='专业挑战室')
    def expert_challenge(self) -> OperationRoundResult:
        op = ExpertChallenge(self.ctx, self.next_plan,
                             need_check_power=self.need_to_check_power_in_mission,
                             can_run_times=None if self.need_to_check_power_in_mission else self.next_can_run_times)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别副本分类', status='恶名狩猎')
    @operation_node(name='恶名狩猎')
    def notorious_hunt(self) -> OperationRoundResult:
        if self.next_plan is None:
            return self.round_fail('没有找到可执行的计划')
        op = NotoriousHunt(self.ctx, self.next_plan,
                           use_charge_power=True,
                           need_check_power=self.need_to_check_power_in_mission,
                           can_run_times=None if self.need_to_check_power_in_mission else self.next_can_run_times)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='实战模拟室', success=True)
    @node_from(from_name='定期清剿', success=True)
    @node_from(from_name='专业挑战室', success=True)
    @node_from(from_name='恶名狩猎', success=True)
    @operation_node(name='挑战成功')
    def challenge_success(self) -> OperationRoundResult:
        # 挑战成功后，重置last_tried_plan以继续查找下一个任务
        self.last_tried_plan = None
        return self.round_success()

    @node_from(from_name='实战模拟室', status=CombatSimulation.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='定期清剿', status=RoutineCleanup.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='专业挑战室', status=ExpertChallenge.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='恶名狩猎', status=NotoriousHunt.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='传送', status='选择失败')
    @node_from(from_name='传送', success=False)
    @operation_node(name='电量不足')
    def charge_not_enough(self) -> OperationRoundResult:
        # 检查自动回复电量设置
        auto_recover_mode = self.ctx.charge_plan_config.auto_recover_charge
        if auto_recover_mode != AutoRecoverChargeEnum.NONE.value.value:
            # 根据设置选择回复方式，尝试回复电量
            return self.round_success(ChargePlanApp.STATUS_TRY_RECOVER_CHARGE)
        
        # 如果没有开启自动回复，执行原来的逻辑
        if self.ctx.charge_plan_config.skip_plan:
            # 跳过当前计划，继续尝试下一个
            if self.next_plan is not None:
                self.last_tried_plan = self.next_plan
            return self.round_success()
        else:
            # 不跳过，直接结束本轮计划
            self.last_tried_plan = None
            return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)

    @node_from(from_name='实战模拟室', success=False)
    @node_from(from_name='定期清剿', success=False)
    @node_from(from_name='专业挑战室', success=False)
    @node_from(from_name='恶名狩猎', success=False)
    @operation_node(name='挑战失败')
    def challenge_failed(self) -> OperationRoundResult:
        return self.round_success()

    @node_from(from_name='电量不足', status=STATUS_TRY_RECOVER_CHARGE)
    @operation_node(name='点击电量文本')
    def click_charge_text(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('菜单', '文本-电量')
        if area is None:
            return self.round_retry('未找到电量区域', wait=1)
        
        # 点击电量文本区域
        self.ctx.controller.click(area.center)
        return self.round_success('已点击电量文本')

    @node_from(from_name='点击电量文本')
    @operation_node(name='选择电量来源')
    def select_charge_source(self) -> OperationRoundResult:
        """根据配置选择电量来源"""
        auto_recover_mode = self.ctx.charge_plan_config.auto_recover_charge
        
        if auto_recover_mode == AutoRecoverChargeEnum.BACKUP_ONLY.value.value:
            # 仅使用储蓄电量
            return self.round_success('使用储蓄电量')
        elif auto_recover_mode == AutoRecoverChargeEnum.ETHER_ONLY.value.value:
            # 仅使用以太电池
            return self.round_success('使用以太电池')
        else:
            # 同时使用（默认先尝试储蓄电量）
            return self.round_success('使用储蓄电量')

    @node_from(from_name='选择电量来源', status='使用储蓄电量')
    @operation_node(name='使用储蓄电量')
    def use_backup_charge(self) -> OperationRoundResult:
        import time
        
        # 等待恢复电量界面出现
        time.sleep(1)
        screen = self.screenshot()
        # 通过OCR识别储蓄电量文本，然后向上偏移点击
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        found_backup_charge = False
        
        for ocr_result, mrl in ocr_result_map.items():
            if '储蓄电量' in ocr_result:
                # 找到储蓄电量文本后，向上移动100个像素点击
                if mrl.max is not None:
                    from one_dragon.base.geometry.point import Point
                    click_point = mrl.max.center
                    # 向上移动100个像素
                    offset_point = Point(click_point.x, click_point.y - 100)
                    self.ctx.controller.click(offset_point)
                    found_backup_charge = True
                    break
        
        if not found_backup_charge:
            return self.round_retry('未找到储蓄电量文本', wait=1)
        
        # 等待界面响应，然后点击确认按钮
        import time
        time.sleep(0.5)
        
        # 点击选择来源的确认按钮
        confirm_area = self.ctx.screen_loader.get_area('恢复电量', '选择来源-确认')
        if confirm_area is not None:
            self.ctx.controller.click(confirm_area.center)
        
        return self.round_success('已选择储蓄电量')

    @node_from(from_name='选择电量来源', status='使用以太电池')
    @node_from(from_name='使用储蓄电量', success=False)
    @node_from(from_name='重新点击电量文本')
    @operation_node(name='使用以太电池')
    def use_ether_battery(self) -> OperationRoundResult:
        import time
        
        # 等待恢复电量界面出现
        time.sleep(1)
        screen = self.screenshot()
        
        # 通过OCR识别以太电池文本，然后向上偏移点击
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        found_ether_battery = False
        
        for ocr_result, mrl in ocr_result_map.items():
            if '以太电池' in ocr_result:
                # 找到以太电池文本后，向上移动100个像素点击
                if mrl.max is not None:
                    from one_dragon.base.geometry.point import Point
                    click_point = mrl.max.center
                    # 向上移动100个像素
                    offset_point = Point(click_point.x, click_point.y - 100)
                    self.ctx.controller.click(offset_point)
                    found_ether_battery = True
                    break
        
        if not found_ether_battery:
            return self.round_retry('未找到以太电池文本', wait=1)
        
        # 等待界面响应，然后点击确认按钮
        time.sleep(0.5)
        
        # 点击选择来源的确认按钮
        confirm_area = self.ctx.screen_loader.get_area('恢复电量', '选择来源-确认')
        if confirm_area is not None:
            self.ctx.controller.click(confirm_area.center)
        
        return self.round_success('已选择以太电池')

    @node_from(from_name='使用储蓄电量')
    @node_from(from_name='使用以太电池')
    @operation_node(name='设置使用数量')
    def set_charge_amount(self) -> OperationRoundResult:
        import time

        # 等待储蓄电量详情界面出现
        time.sleep(1)
        screen = self.screenshot()
        ocr_result_map = self.ctx.ocr.run_ocr(screen)

        # 判断是储蓄电量还是以太电池
        is_backup_charge = False
        saved_power_amount = 0
        for ocr_result, mrl in ocr_result_map.items():
            if '储蓄电量' in ocr_result:
                is_backup_charge = True
                # '储蓄电量×256'
                amount_str = str_utils.get_positive_digits(ocr_result, None)
                if amount_str is not None:
                    saved_power_amount = amount_str
                break

        # 计算需要恢复的电量 - 根据当前计划的实际需求
        if self.next_plan is not None:
            need_charge_power = 1000  # 默认值
            if self.next_plan.category_name == '实战模拟室':
                if self.next_plan.card_num != CardNumEnum.DEFAULT.value.value:
                    need_charge_power = int(self.next_plan.card_num) * 20
            elif self.next_plan.category_name == '定期清剿':
                if not self.ctx.charge_plan_config.use_coupon:
                    need_charge_power = 60
            elif self.next_plan.category_name == '专业挑战室':
                need_charge_power = 40
            elif self.next_plan.category_name == '恶名狩猎':
                need_charge_power = 60
            
            # 检查储蓄电量+当前电量是否足够
            # 这里先获取储蓄电量数量，如果无法获取则假设为0
            backup_charge_amount = 0
            for ocr_result, mrl in ocr_result_map.items():
                if '储蓄电量' in ocr_result:
                    amount_str = str_utils.get_positive_digits(ocr_result, None)
                    if amount_str is not None:
                        backup_charge_amount = amount_str
                    break
            
            total_available_power = self.charge_power + backup_charge_amount
            if total_available_power < need_charge_power:
                return self.round_fail(f'电量不足，需要{need_charge_power}，可用{total_available_power}（当前{self.charge_power}+储蓄{backup_charge_amount}）')
            
            # 计算实际需要的电量
            needed_power = max(0, need_charge_power - self.charge_power)
        else:
            # 如果没有下一个计划，不需要回复电量
            return self.round_fail('没有下一个计划，无需回复电量')
        
        if is_backup_charge:
            if saved_power_amount == 0:
                return self.round_fail('未识别到储蓄电量数量')
            amount_to_use = min(needed_power, saved_power_amount)
        else:  # using ether battery
            # 假设以太电池无限
            amount_to_use = needed_power

        if amount_to_use <= 0:
            return self.round_success('计算出使用数量为0，无需恢复')
        
        # 添加调试信息
        print(f"当前电量: {self.charge_power}, 需要电量: {need_charge_power}, 缺少电量: {needed_power}, 实际使用: {amount_to_use}")

        # 点击输入框
        input_area = self.ctx.screen_loader.get_area('恢复电量', '兑换数量-数字区域')
        if input_area is None:
            return self.round_retry('未找到电量数量输入框', wait=1)
        self.ctx.controller.click(input_area.center)
        time.sleep(0.5)

        # 输入数量
        self.ctx.controller.input_str(str(amount_to_use))
        time.sleep(5)

        return self.round_success('电量数量设置完成')

    @node_from(from_name='设置使用数量')
    @operation_node(name='确认回复电量')
    def confirm_charge_recovery(self) -> OperationRoundResult:
        import time
        
        screen = self.screenshot()
        confirm_area = self.ctx.screen_loader.get_area('恢复电量', '兑换确认')
        if confirm_area is None:
            # 如果没有找到特定区域，尝试通过OCR识别确认按钮
            ocr_result_map = self.ctx.ocr.run_ocr(screen)
            for ocr_result, mrl in ocr_result_map.items():
                if '确认' in ocr_result or '确定' in ocr_result:
                    if mrl.max is not None:
                        self.ctx.controller.click(mrl.max.center)
                        break
            else:
                return self.round_retry('未找到确认按钮', wait=1)
        else:
            self.ctx.controller.click(confirm_area.center)
        
        # 等待电量恢复完成
        time.sleep(2)
        return self.round_success('电量回复完成')

    @node_from(from_name='确认回复电量')
    @operation_node(name='检查回复后电量')
    def check_charge_after_recovery(self) -> OperationRoundResult:
        import time
        
        # 等待电量回复完成
        time.sleep(2)
        
        # 重新打开菜单并检查电量
        op = GotoMenu(self.ctx)
        result = op.execute()
        if not result.success:
            return self.round_by_op_result(result)
        
        # 通过OCR识别当前电量
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('菜单', '文本-电量')
        if area is None:
            return self.round_retry('未找到电量显示区域', wait=1)
            
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        current_charge = str_utils.get_positive_digits(ocr_result, None)
        
        if current_charge is None:
            return self.round_retry('未识别到电量数值', wait=1)

        # 更新当前电量
        self.charge_power = current_charge
        
        # 计算当前计划所需的电量
        if self.next_plan is not None:
            need_charge_power = 1000  # 默认值，表示需要在任务中检查
            
            if self.next_plan.category_name == '实战模拟室':
                if self.next_plan.card_num != CardNumEnum.DEFAULT.value.value:
                    need_charge_power = int(self.next_plan.card_num) * 20
            elif self.next_plan.category_name == '定期清剿':
                if not self.ctx.charge_plan_config.use_coupon:  # 不使用家政券时需要60电量
                    need_charge_power = 60
            elif self.next_plan.category_name == '专业挑战室':
                need_charge_power = 40
            elif self.next_plan.category_name == '恶名狩猎':
                need_charge_power = 60
            
            # 如果能确定所需电量，进行比较
            if need_charge_power != 1000:
                if self.charge_power >= need_charge_power:
                    return self.round_success(f'电量回复成功！当前电量: {current_charge}, 需要电量: {need_charge_power}')
                else:
                    return self.round_fail(f'电量仍不足！当前电量: {current_charge}, 需要电量: {need_charge_power}, 缺少: {need_charge_power - self.charge_power}')
            else:
                # 对于需要在任务中检查的情况，返回成功让后续流程处理
                return self.round_success(f'电量已回复，当前电量: {current_charge}，将在任务执行时检查是否足够')
        
        return self.round_success(f'电量回复完成，当前电量: {current_charge}')

    @node_from(from_name='检查回复后电量', success=True)
    @operation_node(name='回复电量后重新打开菜单')
    def reopen_menu_after_charge_recovery(self) -> OperationRoundResult:
        # 电量回复成功，直接返回成功，菜单已经在检查电量时打开了
        return self.round_success('电量回复成功，准备继续执行计划')

    @node_from(from_name='检查回复后电量', success=False)
    @operation_node(name='电量回复重试')
    def retry_charge_recovery(self) -> OperationRoundResult:
        # 检查重试次数
        if not hasattr(self, 'charge_retry_count'):
            self.charge_retry_count = 0
        
        self.charge_retry_count += 1
        
        if self.charge_retry_count < 3:  # 最多重试2次（总共3次机会）
            return self.round_success('电量仍不足，尝试再次回复')
        else:
            self.charge_retry_count = 0  # 重置计数器
            return self.round_fail('已达到最大重试次数，电量回复失败')

    @node_from(from_name='电量回复重试', success=True)
    @operation_node(name='重新点击电量文本')
    def click_charge_text_retry(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('菜单', '文本-电量')
        if area is None:
            return self.round_retry('未找到电量区域', wait=1)
        
        # 点击电量文本区域
        self.ctx.controller.click(area.center)
        return self.round_success('已重新点击电量文本')

    @node_from(from_name='电量不足', status=STATUS_ROUND_FINISHED)
    @node_from(from_name='电量回复失败', status=STATUS_ROUND_FINISHED)
    @node_from(from_name='查找并选择下一个可执行任务', status=STATUS_ROUND_FINISHED)
    @node_from(from_name='查找并选择下一个可执行任务', success=False)
    @operation_node(name='返回大世界')
    def back_to_world(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='点击电量文本', success=False)
    @node_from(from_name='使用储蓄电量', success=False)
    @node_from(from_name='使用以太电池', success=False)
    @node_from(from_name='设置使用数量', success=False)
    @node_from(from_name='确认回复电量', success=False)
    @node_from(from_name='检查回复后电量', success=False)
    @node_from(from_name='电量回复重试', success=False)
    @node_from(from_name='重新点击电量文本', success=False)
    @operation_node(name='电量回复失败')
    def charge_recovery_failed(self) -> OperationRoundResult:
        # 重置重试计数器
        if hasattr(self, 'charge_retry_count'):
            self.charge_retry_count = 0
            
        # 如果电量回复失败，执行原来的跳过逻辑
        if self.ctx.charge_plan_config.skip_plan:
            # 跳过当前计划，继续尝试下一个
            if self.next_plan is not None:
                self.last_tried_plan = self.next_plan
            return self.round_success()
        else:
            # 不跳过，直接结束本轮计划
            self.last_tried_plan = None
            return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)
