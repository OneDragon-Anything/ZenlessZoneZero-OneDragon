from typing import ClassVar

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.application.notorious_hunt import notorious_hunt_const
from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntConfig
from zzz_od.application.notorious_hunt.notorious_hunt_run_record import (
    NotoriousHuntRunRecord,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.challenge_mission.check_next_after_battle import (
    ChooseNextOrFinishAfterBattle,
)
from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt
from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium


class NotoriousHuntApp(ZApplication):

    STATUS_NO_PLAN: ClassVar[str] = '未配置恶名狩猎计划'
    STATUS_ROUND_FINISHED: ClassVar[str] = '本轮计划已完成'

    def __init__(self, ctx: ZContext):
        """
        恶名狩猎
        """
        ZApplication.__init__(
            self,
            ctx=ctx, app_id=notorious_hunt_const.APP_ID,
            op_name=notorious_hunt_const.APP_NAME,
        )

        self.config: NotoriousHuntConfig = self.ctx.run_context.get_config(
            app_id=notorious_hunt_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.run_record: NotoriousHuntRunRecord = self.ctx.run_context.get_run_record(
            app_id=notorious_hunt_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
        )

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        self.next_plan: ChargePlanItem | None = None
        self.last_tried_plan: ChargePlanItem | None = None

    @operation_node(name='开始恶名狩猎', is_start_node=True)
    def start_hunt(self) -> OperationRoundResult:
        # 每轮开始复位游标并清空本轮跳过标记
        self.last_tried_plan = None
        for plan in self.config.plan_list:
            plan.skipped = False
        return self.round_success()

    @node_from(from_name='开始恶名狩猎')
    @node_from(from_name='跳过或结束计划')
    @node_from(from_name='判断剩余次数')
    @operation_node(name='查找下一条计划')
    def find_next_plan(self) -> OperationRoundResult:
        if len(self.config.plan_list) == 0:
            return self.round_success(NotoriousHuntApp.STATUS_NO_PLAN)

        # 全部计划已完成：开启循环则清零重开，否则结束本轮
        if self.config.all_plan_finished():
            if self.config.loop:
                self.last_tried_plan = None
                self.config.reset_plans()
            else:
                return self.round_success(NotoriousHuntApp.STATUS_ROUND_FINISHED)

        self.next_plan = self.config.get_next_plan(self.last_tried_plan)
        if self.next_plan is None:
            return self.round_success(NotoriousHuntApp.STATUS_ROUND_FINISHED)
        return self.round_success()

    @node_from(from_name='查找下一条计划')
    @operation_node(name='传送')
    def transport(self) -> OperationRoundResult:
        op = TransportByCompendium(self.ctx,
                                   self.next_plan.tab_name,
                                   self.next_plan.category_name,
                                   self.next_plan.mission_type_name)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送', success=False, status='找不到 代理人方案培养')
    @node_from(from_name='恶名狩猎', status=ChooseNextOrFinishAfterBattle.STATUS_AGENT_PLAN_FINISHED)
    @operation_node(name='跳过或结束计划')
    def skip_plan_or_finish(self) -> OperationRoundResult:
        # 特训目标找不到代理人头像或已达成，提前跳过/结束
        self.next_plan.skipped = True
        self.last_tried_plan = self.next_plan
        return self.round_success()

    @node_from(from_name='传送')
    @operation_node(name='恶名狩猎')
    def notorious_hunt(self) -> OperationRoundResult:
        op = NotoriousHunt(self.ctx, self.next_plan, use_charge_power=False)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='恶名狩猎', success=True)
    @node_from(from_name='恶名狩猎', success=False)
    @operation_node(name='判断剩余次数')
    def check_left_times(self) -> OperationRoundResult:
        if self.run_record.left_times == 0:
            return self.round_success(NotoriousHunt.STATUS_NO_LEFT_TIMES)

        if self.previous_node.is_success:
            # 成功完成一次后复位游标，从头重新查找
            self.last_tried_plan = None
        else:
            # 战斗失败：标记当前计划本轮跳过，避免在同一轮里反复死磕
            self.next_plan.skipped = True
            self.last_tried_plan = self.next_plan
        return self.round_success()

    @node_from(from_name='判断剩余次数', status=NotoriousHunt.STATUS_NO_LEFT_TIMES)
    @node_from(from_name='恶名狩猎', status=NotoriousHunt.STATUS_NO_LEFT_TIMES)
    @node_from(from_name='查找下一条计划', status=STATUS_NO_PLAN)
    @node_from(from_name='查找下一条计划', status=STATUS_ROUND_FINISHED)
    @operation_node(name='点击奖励入口')
    def click_reward_entry(self) -> OperationRoundResult:
        return self.round_by_click_area(
            '恶名狩猎', '奖励入口',
            success_wait=1, retry_wait=1
        )

    @node_from(from_name='点击奖励入口')
    @node_notify(when=NotifyTiming.CURRENT_DONE)
    @operation_node(name='全部领取', node_max_retry_times=2)
    def claim_all(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot, '恶名狩猎', '全部领取',
            success_wait=1, retry_wait=0.5
        )

    @node_from(from_name='点击奖励入口', success=False)
    @node_from(from_name='全部领取')
    @node_from(from_name='全部领取', success=False)
    @operation_node(name='返回大世界')
    def back_to_world(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())
