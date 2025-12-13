import time
from typing import ClassVar

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import node_notify, NotifyTiming
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.challenge_mission.check_next_after_battle import (
    ChooseNextOrFinishAfterBattle,
)
from zzz_od.operation.challenge_mission.exit_in_battle import ExitInBattle
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam
from zzz_od.operation.compendium.coupon import Coupon
from zzz_od.operation.deploy import Deploy
from zzz_od.operation.restore_charge import RestoreCharge
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum


class AreaPatrol(ZOperation):

    STATUS_CHARGE_NOT_ENOUGH: ClassVar[str] = '电量不足'
    STATUS_FIGHT_TIMEOUT: ClassVar[str] = '战斗超时'

    def __init__(self, ctx: ZContext, plan: ChargePlanItem):
        """
        使用快捷手册传送后
        用这个进行挑战
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name='%s %s' % (
                gt('区域巡防', 'game'),
                gt(plan.mission_type_name, 'game')
            )
        )
        self.config: ChargePlanConfig = self.ctx.run_context.get_config(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.plan: ChargePlanItem = plan

    @operation_node(name='等待入口加载', is_start_node=True, node_max_retry_times=60)
    def wait_entry_load(self) -> OperationRoundResult:
        return self.round_by_find_area(
            self.last_screenshot, '实战模拟室', '挑战等级',
            success_wait=1, retry_wait=1
        )

    # 传送过来已经是对的副本了
    # @node_from(from_name='等待入口加载')
    # @operation_node(name='选择副本')
    def choose_mission(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('区域巡防', '副本名称列表')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)

        target_point: Point | None = None
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        for ocr_result, mrl in ocr_result_map.items():
            if not str_utils.find_by_lcs(gt(self.plan.mission_type_name, 'game'), ocr_result, percent=0.5):
                continue

            target_point = area.left_top + mrl.max + Point(0, 50)
            break

        if target_point is None:
            start = area.center
            end = start + Point(-100, 0)
            self.ctx.controller.drag_to(start=start, end=end)
            return self.round_retry(status=f'找不到 {self.plan.mission_type_name}', wait=1)

        self.ctx.controller.click(target_point)
        return self.round_success(wait=1)

    @node_from(from_name='等待入口加载')
    @operation_node(name='处理家政券')
    def handle_coupon(self) -> OperationRoundResult:
        op = Coupon(self.ctx, self.plan)
        if self.config.use_coupon:
            return self.round_by_op_result(op.execute())
        else:
            return self.round_success(Coupon.STATUS_CONTINUE_RUN_WITH_CHARGE)

    @node_from(from_name='处理家政券', success=False)
    @node_from(from_name='处理家政券', status=Coupon.STATUS_CONTINUE_RUN_WITH_CHARGE)
    @node_from(from_name='恢复电量', status='恢复电量成功')
    @operation_node(name='下一步', node_max_retry_times=10)  # 部分机器加载较慢 延长出战的识别时间
    def click_next(self) -> OperationRoundResult:
        # 防止前面电量识别错误
        result = self.round_by_find_area(self.last_screenshot, '恢复电量', '标题')
        if result.is_success:
            return self.round_success(status=AreaPatrol.STATUS_CHARGE_NOT_ENOUGH)

        # 点击直到出战按钮出现
        result = self.round_by_find_area(self.last_screenshot, '实战模拟室', '出战')
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_and_click_area(self.last_screenshot, '实战模拟室', '下一步')
        if result.is_success:
            time.sleep(0.5)
            self.ctx.controller.mouse_move(ScreenNormalWorldEnum.UID.value.center)  # 点击后 移开鼠标 防止识别不到出战
            return self.round_wait(result.status, wait=0.5)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='下一步', status=STATUS_CHARGE_NOT_ENOUGH)
    @operation_node(name='恢复电量')
    def restore_charge(self) -> OperationRoundResult:
        if not self.config.is_restore_charge_enabled:
            return self.round_success(AreaPatrol.STATUS_CHARGE_NOT_ENOUGH)
        op = RestoreCharge(self.ctx)
        result = self.round_by_op_result(op.execute())
        return result if result.is_success else self.round_success(AreaPatrol.STATUS_CHARGE_NOT_ENOUGH)

    @node_from(from_name='下一步', status='出战')
    @operation_node(name='选择预备编队')
    def choose_predefined_team(self) -> OperationRoundResult:
        if self.plan.predefined_team_idx == -1:
            return self.round_success('无需选择预备编队')
        else:
            op = ChoosePredefinedTeam(self.ctx, [self.plan.predefined_team_idx])
            return self.round_by_op_result(op.execute())

    @node_from(from_name='选择预备编队')
    @operation_node(name='出战')
    def deploy(self) -> OperationRoundResult:
        op = Deploy(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='出战')
    @node_from(from_name='判断下一次', status='战斗结果-再来一次')
    @operation_node(name='加载自动战斗指令')
    def init_auto_battle(self) -> OperationRoundResult:
        if self.plan.predefined_team_idx == -1:
            auto_battle = self.plan.auto_battle_config
        else:
            team_list = self.ctx.team_config.team_list
            auto_battle = team_list[self.plan.predefined_team_idx].auto_battle

        self.ctx.auto_battle_context.init_auto_op(
            sub_dir='auto_battle',
            op_name=auto_battle,
        )
        return self.round_success()

    @node_from(from_name='加载自动战斗指令')
    @operation_node(name='等待战斗画面加载', node_max_retry_times=60)
    def wait_battle_screen(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击', retry_wait_round=1)
        return result

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='向前移动准备战斗')
    def move_to_battle(self) -> OperationRoundResult:
        self.ctx.controller.move_w(press=True, press_time=1, release=True)
        self.ctx.auto_battle_context.start_auto_battle()
        return self.round_success()

    @node_from(from_name='向前移动准备战斗')
    @operation_node(name='自动战斗', mute=True, timeout_seconds=600)
    def auto_battle(self) -> OperationRoundResult:
        if self.ctx.auto_battle_context.last_check_end_result is not None:
            self.ctx.auto_battle_context.stop_auto_battle()
            return self.round_success(status=self.ctx.auto_battle_context.last_check_end_result)

        self.ctx.auto_battle_context.check_battle_state(
            self.last_screenshot, self.last_screenshot_time,
            check_battle_end_normal_result=True)

        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='自动战斗')
    @node_notify(when=NotifyTiming.CURRENT_SUCCESS, detail=True)
    @operation_node(name='战斗结束')
    def after_battle(self) -> OperationRoundResult:
        self.config.add_plan_run_times(self.plan)
        return self.round_success()

    @node_from(from_name='战斗结束')
    @operation_node(name='判断下一次')
    def check_next(self) -> OperationRoundResult:
        op = ChooseNextOrFinishAfterBattle(self.ctx, self.plan.plan_times > self.plan.run_times)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='自动战斗', success=False, status=Operation.STATUS_TIMEOUT)
    @operation_node(name='战斗超时')
    def battle_timeout(self) -> OperationRoundResult:
        self.ctx.auto_battle_context.stop_auto_battle()
        op = ExitInBattle(self.ctx, '战斗-挑战结果-失败', '按钮-退出')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='战斗超时')
    @operation_node(name='点击挑战结果退出')
    def click_result_exit(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(screen_name='战斗-挑战结果-失败', area_name='按钮-退出',
                                                   until_not_find_all=[('战斗-挑战结果-失败', '按钮-退出')],
                                                   success_wait=1, retry_wait=1)
        if result.is_success:
            return self.round_fail(status=AreaPatrol.STATUS_FIGHT_TIMEOUT)
        else:
            return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='自动战斗', status='普通战斗-撤退')
    @operation_node(name='战斗失败')
    def battle_fail(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(self.last_screenshot, '战斗画面', '战斗结果-撤退')
        if result.is_success:
            return self.round_success(result.status, wait=5)

        return self.round_retry(result.status, wait=1)

    def handle_pause(self):
        self.ctx.auto_battle_context.stop_auto_battle()

    def handle_resume(self):
        if self.current_node.node is not None and self.current_node.node.cn == '自动战斗':
            self.ctx.auto_battle_context.resume_auto_battle()


def __debug_charge():
    """
    测试电量识别
    @return:
    """
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('_1742622263371')
    area = ctx.screen_loader.get_area('区域巡防', '剩余电量')
    part = cv2_utils.crop_image_only(screen, area.rect)
    ocr_result = ctx.ocr.run_ocr_single_line(part)
    print(ocr_result)


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    plan = ChargePlanItem(
        category_name='区域巡防',
        mission_type_name='铁律与狂徒',
        auto_battle_config='全配队通用',
        predefined_team_idx=0
    )
    op = AreaPatrol(ctx, plan)
    op.execute()


if __name__ == '__main__':
    __debug()
