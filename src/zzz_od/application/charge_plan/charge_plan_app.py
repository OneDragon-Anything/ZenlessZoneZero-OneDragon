import time
from typing import ClassVar, Optional

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.zzz_application import ZApplication
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem, CardNumEnum, RestoreChargeEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.compendium.combat_simulation import CombatSimulation
from zzz_od.operation.compendium.expert_challenge import ExpertChallenge
from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt
from zzz_od.operation.compendium.routine_cleanup import RoutineCleanup
from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium
from zzz_od.operation.goto.goto_menu import GotoMenu
from zzz_od.operation.restore_charge import RestoreCharge


class ChargePlanApp(ZApplication):

    STATUS_NO_PLAN: ClassVar[str] = '没有可运行的计划'
    STATUS_ROUND_FINISHED: ClassVar[str] = '已完成一轮计划'
    STATUS_TRY_RECOVER_CHARGE: ClassVar[str] = '尝试恢复电量'

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

    @operation_node(name='开始体力计划', is_start_node=True)
    def start_charge_plan(self) -> OperationRoundResult:
        # 每次新一轮计划开始时，重置计划状态
        self.last_tried_plan = None
        return self.round_success()

    @node_from(from_name='挑战成功')
    @node_from(from_name='挑战失败')
    @node_from(from_name='开始体力计划')
    @node_from(from_name='电量不足')
    @node_from(from_name='电量恢复失败')
    @node_from(from_name='恢复电量后重新打开菜单')
    @operation_node(name='打开菜单')
    def goto_menu(self) -> OperationRoundResult:
        op = GotoMenu(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='打开菜单')
    @operation_node(name='识别电量')
    def check_charge_power(self) -> OperationRoundResult:
        # 不能在快捷手册里面识别电量 因为每个人的备用电量不一样
        area = self.ctx.screen_loader.get_area('菜单', '文本-电量')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
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
        如果电量不足且开启了恢复电量，则尝试恢复电量
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

        # 如果电量不足且开启了恢复电量
        if self.charge_power < min_required_power and self.ctx.charge_plan_config.restore_charge != RestoreChargeEnum.NONE.value.value:
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
                # 如果开启了恢复电量，允许继续执行以触发恢复流程
                if self.ctx.charge_plan_config.restore_charge != RestoreChargeEnum.NONE.value.value:
                    # 设置下一个计划并继续，让传送阶段处理电量不足
                    self.next_plan = candidate_plan
                    return self.round_success()
                # 如果没有开启恢复电量，执行原来的逻辑
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

        return self.round_fail(ChargePlanApp.STATUS_NO_PLAN)

    @node_from(from_name='查找并选择下一个可执行任务')
    @operation_node(name='传送')
    def transport(self) -> OperationRoundResult:
        # 如果开启了恢复电量，在传送前再次检查电量
        if self.ctx.charge_plan_config.restore_charge != RestoreChargeEnum.NONE.value.value:
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
                return self.round_fail('电量不足，需要恢复')

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
    @node_from(from_name='传送', success=False, status='找不到 代理人方案培养')
    @operation_node(name='电量不足')
    def charge_not_enough(self) -> OperationRoundResult:
        # 检查恢复电量设置
        auto_recover_mode = self.ctx.charge_plan_config.restore_charge
        if auto_recover_mode != RestoreChargeEnum.NONE.value.value:
            # 根据设置选择恢复方式，尝试恢复电量
            return self.round_success(ChargePlanApp.STATUS_TRY_RECOVER_CHARGE)

        # 如果没有开启恢复电量，执行原来的逻辑
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
    @operation_node(name='恢复电量')
    def restore_charge(self) -> OperationRoundResult:
        """使用新的RestoreCharge operation来恢复电量"""
        # 计算所需电量
        required_charge = 1000  # 默认值
        if self.next_plan is not None:
            if self.next_plan.category_name == '实战模拟室':
                if self.next_plan.card_num != CardNumEnum.DEFAULT.value.value:
                    required_charge = int(self.next_plan.card_num) * 20
            elif self.next_plan.category_name == '定期清剿':
                if not self.ctx.charge_plan_config.use_coupon:
                    required_charge = 60
            elif self.next_plan.category_name == '专业挑战室':
                required_charge = 40
            elif self.next_plan.category_name == '恶名狩猎':
                required_charge = 60

        # 创建并执行恢复电量操作
        op = RestoreCharge(
            self.ctx,
            current_charge=self.charge_power,
            required_charge=required_charge,
            restore_mode=self.ctx.charge_plan_config.restore_charge
        )
        result = op.execute()

        if result.success:
            # 更新当前电量
            self.charge_power = op.current_charge
            return self.round_success('电量恢复成功')
        else:
            return self.round_fail('电量恢复失败')

    @node_from(from_name='恢复电量', success=True)
    @operation_node(name='恢复电量后重新打开菜单')
    def reopen_menu_after_restore_charge(self) -> OperationRoundResult:
        # 电量恢复成功，直接返回成功，菜单已经在恢复电量时打开了
        return self.round_success('电量恢复成功，准备继续执行计划')

    @node_from(from_name='电量不足', status=STATUS_ROUND_FINISHED)
    @node_from(from_name='恢复电量', success=False)
    @node_from(from_name='查找并选择下一个可执行任务', status=STATUS_ROUND_FINISHED)
    @node_from(from_name='查找并选择下一个可执行任务', success=False)
    @operation_node(name='返回大世界')
    def back_to_world(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='恢复电量', success=False)
    @operation_node(name='电量恢复失败')
    def restore_charge_failed(self) -> OperationRoundResult:
        # 如果电量恢复失败，执行原来的跳过逻辑
        if self.ctx.charge_plan_config.skip_plan:
            # 跳过当前计划，继续尝试下一个
            if self.next_plan is not None:
                self.last_tried_plan = self.next_plan
            return self.round_success()
        else:
            # 不跳过，直接结束本轮计划
            self.last_tried_plan = None
            return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)
