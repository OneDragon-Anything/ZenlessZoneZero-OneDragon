from typing import ClassVar, Optional

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.notorious_hunt import notorious_hunt_const
from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntConfig
from zzz_od.application.zzz_application import ZApplication
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.compendium.combat_simulation import CombatSimulation
from zzz_od.operation.compendium.expert_challenge import ExpertChallenge
from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt
from zzz_od.operation.compendium.routine_cleanup import RoutineCleanup
from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium


class NotoriousHuntApp(ZApplication):

    STATUS_NO_PLAN: ClassVar[str] = '未配置恶名狩猎计划'

    def __init__(self, ctx: ZContext):
        """
        每天自动接收邮件奖励
        """
        ZApplication.__init__(
            self,
            ctx=ctx, app_id=notorious_hunt_const.APP_ID,
            op_name=gt(notorious_hunt_const.APP_NAME),
            need_notify=True,
        )

        self.config: Optional[NotoriousHuntConfig] = self.ctx.run_context.get_config(
            app_id=notorious_hunt_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        self.next_plan: Optional[ChargePlanItem] = None

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        next_plan = self.config.get_next_plan()
        if next_plan is None:
            return self.round_fail(NotoriousHuntApp.STATUS_NO_PLAN)

        self.next_plan = next_plan
        op = TransportByCompendium(self.ctx,
                                   next_plan.tab_name,
                                   next_plan.category_name,
                                   next_plan.mission_type_name)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @node_from(from_name='判断剩余次数')
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
        else:
            self.next_plan = self.config.get_next_plan()
            return self.round_success()

    @node_from(from_name='判断剩余次数', status=NotoriousHunt.STATUS_NO_LEFT_TIMES)
    @node_from(from_name='恶名狩猎', status=NotoriousHunt.STATUS_NO_LEFT_TIMES)
    @operation_node(name='点击奖励入口')
    def click_reward_entry(self) -> OperationRoundResult:
        return self.round_by_click_area(
            '恶名狩猎', '奖励入口',
            success_wait=1, retry_wait=1
        )

    @node_from(from_name='点击奖励入口')
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
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())
