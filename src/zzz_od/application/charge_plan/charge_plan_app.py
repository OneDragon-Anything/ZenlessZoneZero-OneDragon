from typing import ClassVar

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
)
from zzz_od.application.charge_plan.charge_plan_run_record import ChargePlanRunRecord
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.compendium.area_patrol import AreaPatrol
from zzz_od.operation.compendium.combat_simulation import CombatSimulation
from zzz_od.operation.compendium.expert_challenge import ExpertChallenge
from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt
from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium
from zzz_od.operation.goto.goto_menu import GotoMenu
from zzz_od.operation.restore_charge import RestoreCharge


class ChargePlanApp(ZApplication):

    STATUS_NO_PLAN: ClassVar[str] = '没有可运行的计划'
    STATUS_ROUND_FINISHED: ClassVar[str] = '已完成一轮计划'
    STATUS_TRY_RESTORE_CHARGE: ClassVar[str] = '尝试恢复电量'

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=charge_plan_const.APP_ID,
            op_name=charge_plan_const.APP_NAME,
        )
        self.config: ChargePlanConfig = self.ctx.run_context.get_config(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: ChargePlanRunRecord = self.ctx.run_context.get_run_record(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
        )

        self.charge_power: int = 0  # 剩余电量
        self.required_charge: int = 0  # 需要的电量
        self.last_tried_plan: ChargePlanItem | None = None
        self.current_plan: ChargePlanItem | None = None

    @operation_node(name='开始体力计划', is_start_node=True)
    def start_charge_plan(self) -> OperationRoundResult:
        self.last_tried_plan = None
        for plan in self.config.plan_list:
            plan.skipped = False
        return self.round_success()

    @node_from(from_name='挑战完成')
    @node_from(from_name='开始体力计划')
    @node_from(from_name='跳过或结束计划')
    @node_from(from_name='恢复电量', success=True)
    @node_from(from_name='恢复电量', success=False)
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
        self.run_record.record_current_charge_power(digit)
        return self.round_success(f'剩余电量 {digit}')

    @node_from(from_name='识别电量')
    @operation_node(name='查找并选择下一个可执行任务')
    def find_and_select_next_plan(self) -> OperationRoundResult:
        """
        查找计划列表中的下一个可执行任务（未完成且体力足够）。
        如果找到，更新 self.next_plan 并返回成功状态。
        如果找不到，返回计划完成状态。
        """
        # 检查是否所有计划都已完成
        if self.config.all_plan_finished():
            # 如果开启了循环模式且所有计划已完成，重置计划并继续
            if self.config.loop:
                self.last_tried_plan = None
                self.config.reset_plans()
            else:
                return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)

        # 使用循环查找下一个可执行的任务
        while True:
            # 查找下一个未完成的计划
            candidate_plan = self.config.get_next_plan(self.last_tried_plan)
            if candidate_plan is None:
                return self.round_fail(ChargePlanApp.STATUS_NO_PLAN)

            # 计算当前计划预估所需电量；未知类型会返回0，交给副本内流程继续判断
            need_charge_power = candidate_plan.estimated_charge_power

            # 检查电量是否足够
            if need_charge_power > 0 and self.charge_power < need_charge_power:
                if (
                    not self.config.is_restore_charge_enabled
                    or (self.node_status.get('恢复电量') and self.node_status.get('恢复电量').is_fail)
                ):
                    if not self.config.skip_plan:
                        return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)
                    else:
                        # 跳过当前计划，继续查找下一个任务
                        self.last_tried_plan = candidate_plan
                        continue
                else:
                    # 设置下一个计划，然后触发恢复电量
                    self.current_plan = candidate_plan
                    self.required_charge = need_charge_power - self.charge_power
                    return self.round_success(ChargePlanApp.STATUS_TRY_RESTORE_CHARGE)

            # 设置下一个计划并返回成功
            self.current_plan = candidate_plan
            return self.round_success()

    @node_from(from_name='查找并选择下一个可执行任务')
    @node_from(from_name='恢复电量', status='继续前往副本')
    @operation_node(name='传送')
    def transport(self) -> OperationRoundResult:
        # 使用已经在查找并选择下一个可执行任务节点中设置好的self.current_plan
        op = TransportByCompendium(self.ctx,
                                   self.current_plan.tab_name,
                                   self.current_plan.category_name,
                                   self.current_plan.mission_type_name)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='识别副本分类')
    def check_mission_type(self) -> OperationRoundResult:
        return self.round_success(self.current_plan.category_name)

    @node_from(from_name='识别副本分类', status='实战模拟室')
    @operation_node(name='实战模拟室')
    def combat_simulation(self) -> OperationRoundResult:
        op = CombatSimulation(self.ctx, self.current_plan)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别副本分类', status='区域巡防')
    @operation_node(name='区域巡防')
    def area_patrol(self) -> OperationRoundResult:
        op = AreaPatrol(self.ctx, self.current_plan)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别副本分类', status='专业挑战室')
    @operation_node(name='专业挑战室')
    def expert_challenge(self) -> OperationRoundResult:
        op = ExpertChallenge(self.ctx, self.current_plan)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别副本分类', status='恶名狩猎')
    @operation_node(name='恶名狩猎')
    def notorious_hunt(self) -> OperationRoundResult:
        op = NotoriousHunt(self.ctx, self.current_plan, use_charge_power=True)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='实战模拟室', success=True)
    @node_from(from_name='实战模拟室', success=False)
    @node_from(from_name='区域巡防', success=True)
    @node_from(from_name='区域巡防', success=False)
    @node_from(from_name='专业挑战室', success=True)
    @node_from(from_name='专业挑战室', success=False)
    @node_from(from_name='恶名狩猎', success=True)
    @node_from(from_name='恶名狩猎', success=False)
    @operation_node(name='挑战完成')
    def challenge_complete(self) -> OperationRoundResult:
        # 成功后继续正常轮转；失败则标记当前计划已跳过，避免在同一轮里死循环重试
        if self.previous_node.is_success:
            self.last_tried_plan = None
        else:
            self.current_plan.skipped = True
            self.last_tried_plan = self.current_plan
        return self.round_success()

    @node_from(from_name='实战模拟室', status=CombatSimulation.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='区域巡防', status=AreaPatrol.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='专业挑战室', status=ExpertChallenge.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='恶名狩猎', status=NotoriousHunt.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='恶名狩猎', status=NotoriousHunt.STATUS_BLOCKED_BY_LEFT_TIMES)
    @node_from(from_name='恢复电量', status=RestoreCharge.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='传送', success=False, status='找不到 代理人方案培养')
    @operation_node(name='跳过或结束计划')
    def skip_plan_or_finish(self) -> OperationRoundResult:
        is_agent_plan = self.current_plan.is_agent_plan
        is_blocked_by_left_times = self.previous_node.status == NotoriousHunt.STATUS_BLOCKED_BY_LEFT_TIMES
        if self.config.skip_plan or is_agent_plan or is_blocked_by_left_times:
            # 标记当前计划为跳过，继续尝试下一个
            self.current_plan.skipped = True
            self.last_tried_plan = self.current_plan
            return self.round_success()
        else:
            # 不跳过，直接结束本轮计划
            self.last_tried_plan = None
            return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)

    @node_from(from_name='查找并选择下一个可执行任务', status=STATUS_TRY_RESTORE_CHARGE)
    @operation_node(name='恢复电量', save_status=True)
    def restore_charge(self) -> OperationRoundResult:
        op = RestoreCharge(
            self.ctx,
            self.required_charge,
            is_menu=True
        )
        return self.round_by_op_result(op.execute())

    @node_from(from_name='跳过或结束计划', status=STATUS_ROUND_FINISHED)
    @node_from(from_name='查找并选择下一个可执行任务', status=STATUS_ROUND_FINISHED)
    @node_from(from_name='查找并选择下一个可执行任务', success=False)
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='返回大世界')
    def back_to_world(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        op_result = op.execute()
        return self.round_by_op_result(op_result, status=f'剩余电量 {self.charge_power}')


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = ChargePlanApp(ctx)
    app.config.plan_list = [
        ChargePlanItem(
            tab_name='训练',
            category_name='恶名狩猎',
            mission_type_name='猎血清道夫',
            level='默认等级',
            auto_battle_config='全配队通用',
            plan_times=1,
            predefined_team_idx=-1,
        )
    ]
    app.config.data['loop'] = False
    app.execute()


if __name__ == '__main__':
    __debug()
