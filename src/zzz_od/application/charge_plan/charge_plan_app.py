from typing import ClassVar

import cv2

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.log_utils import log
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanConfig,
    ChargePlanItem,
    RestoreChargeEnum,
)
from zzz_od.application.charge_plan.charge_plan_run_record import ChargePlanRunRecord
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.challenge_mission.check_next_after_battle import (
    ChooseNextOrFinishAfterBattle,
)
from zzz_od.operation.compendium.area_patrol import AreaPatrol
from zzz_od.operation.compendium.combat_simulation import CombatSimulation
from zzz_od.operation.compendium.expert_challenge import ExpertChallenge
from zzz_od.operation.compendium.notorious_hunt import NotoriousHunt
from zzz_od.operation.compendium.tp_by_compendium import TransportByCompendium


class ChargePlanApp(ZApplication):

    STATUS_NO_PLAN: ClassVar[str] = '没有可运行的计划'
    STATUS_ROUND_FINISHED: ClassVar[str] = '已完成一轮计划'
    STATUS_FIND_NEXT_PLAN: ClassVar[str] = '继续查找下一个计划'

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

        self.battery_charge: int = 0  # 电量
        self.backup_battery_charge: int = 0  # 储蓄电量
        self.ether_battery: int = 0  # 以太电池数量
        self.temp_plan: ChargePlanItem | None = None  # 本次运行临时插入的计划
        self.last_tried_plan: ChargePlanItem | None = None
        self.current_plan: ChargePlanItem | None = None
        self.double_reward_checked: bool = False  # 本次运行是否已检查过双倍活动

    @operation_node(name='开始体力计划', is_start_node=True)
    def start_charge_plan(self) -> OperationRoundResult:
        self.temp_plan = None
        self.last_tried_plan = None
        self.double_reward_checked = False
        for plan in self.config.plan_list:
            plan.skipped = False
        current_dt = self.run_record.get_current_dt()
        if self.config.try_reset_plan_times_by_dt(current_dt):
            log.info('已按游戏刷新日重置体力计划已运行次数 %s', current_dt)
        return self.round_success()

    @node_from(from_name='挑战完成')
    @node_from(from_name='开始体力计划')
    @node_from(from_name='跳过或结束计划', status=STATUS_FIND_NEXT_PLAN)
    @operation_node(name='前往大世界')
    def back_before_open_compendium(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx, ensure_normal_world=True)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='前往大世界')
    @operation_node(name='打开快捷手册')
    def open_compendium(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='快捷手册-训练')

    @node_from(from_name='打开快捷手册')
    @node_notify(when=NotifyTiming.CURRENT_FAIL)
    @operation_node(name='识别电量')
    def check_battery_charge(self) -> OperationRoundResult:
        """识别快捷手册资源栏中的电量、储蓄电量和以太电池。

        框架 OCR 的常规入口会先对整条资源栏检测文字位置，再按检测框筛选数字；图标、分隔线和“/240”会使该步骤漏识单字符或串入上限。
        由于三个数字的活动范围固定，这里不直接调用整栏检测入口，而是先按配置颜色提取文字，再按固定位置分成三个互不相交且留有间隔的字段。
        字段切分后仍复用框架提供的 OCR 模型和识别接口，只对每个已知字段执行单行识别；对比测试表明，该方案准确率、稳定性和执行开销更好。
        """
        area = self.ctx.screen_loader.get_area('快捷手册', '资源栏')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        mask = cv2.inRange(part, area.color_range_lower, area.color_range_upper)
        mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
        # 资源栏右对齐，某项数字变长时会推动自身及左侧字段左移；
        # 三个 ROI 按电量 3 位、储蓄电量 4 位（2400）、以太电池 3 位（300）的上限预留，仍不会相互串入。
        resource_list = [
            self.ctx.ocr.run_ocr_single_line(mask[y1:y2, x1:x2], strict_one_line=True)
            for x1, y1, x2, y2 in ((75, 8, 225, 72), (275, 8, 410, 72), (425, 8, 535, 72))
        ]
        log.debug('快捷手册资源栏 OCR %s', resource_list)

        battery_charge = str_utils.get_positive_digits(resource_list[0], None)
        backup_battery_charge = str_utils.get_positive_digits(resource_list[1], None)
        ether_battery = str_utils.get_positive_digits(resource_list[2], None)
        if battery_charge is None or backup_battery_charge is None or ether_battery is None:
            return self.round_retry('未识别到电量', wait=1)

        self.battery_charge = battery_charge
        self.backup_battery_charge = backup_battery_charge
        self.ether_battery = ether_battery
        self.run_record.record_current_charge_power(self.battery_charge)
        log.info('剩余电量 %s 储蓄电量 %s 以太电池 %s', self.battery_charge, self.backup_battery_charge, self.ether_battery)
        if self.config.double_reward and not self.double_reward_checked:
            self.double_reward_checked = True
            return self.round_success('查看双倍活动')
        return self.round_success('查找候选计划')

    @node_from(from_name='识别电量', status='查看双倍活动')
    @operation_node(name='查看双倍活动')
    def check_double_reward_event(self) -> OperationRoundResult:
        """
        实战模拟室的每日双倍总数都是5次, 刷盘子的2次暂不考虑. 理由:
        1. 如果没抽角色, 体力没事干的时候就去屯金盘收益最高, 此时体力计划能顺便覆盖盘子双倍
        2. 双倍盘子活动出现的时机一般在卡池开了之后几天, 此时如果抽了角色也差不多养好了要刷盘子了
        3. 双倍基础材料活动都是在版本末期, 没事干的时候整一出双倍材料, 总不能没事干的时候一直刷基础材料吧.
           这个活动就显得很鸡肋, 像是专门给预抽卡的人群(比如氪佬)设计的
        """

        op = TransportByCompendium(self.ctx, '训练', '实战模拟室')
        result1 = self.round_by_op_result(op.execute())
        if not result1.is_success:
            return result1

        # 查看剩余几次的文字
        result1 = self.round_by_find_area(
            self.screenshot(), '快捷手册', '每日怪物卡双倍掉落次数'
        )
        if not result1.is_success:
            return self.round_success('无双倍活动')
        # ocr 检测剩余次数
        area = self.ctx.screen_loader.get_area('快捷手册', '怪物卡双倍剩余次数')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        digit = str_utils.get_positive_digits(ocr_result, None)
        if digit is None:
            return self.round_retry('双倍活动识别出错', wait=1)
        times_left = digit // 10
        if times_left == 0 or digit % 10 != 5:
            return self.round_success('无双倍活动')
        # 识别出错
        if times_left > 5:
            return self.round_retry('双倍活动识别出错', wait=1)

        card_num = min(self.battery_charge // 20, times_left)
        if card_num <= 0:
            self.temp_plan = None
            return self.round_success('无双倍活动')

        temp_plan = self.config.combat_simulation_double_reward_config
        temp_plan.skipped = False
        temp_plan.run_times = 1
        temp_plan.plan_times = 1
        temp_plan.card_num = str(card_num)

        self.temp_plan = temp_plan
        return self.round_success()

    @node_from(from_name='识别电量', status='查找候选计划')
    @node_from(from_name='查看双倍活动')
    @node_from(from_name='查看双倍活动', success=False)
    @node_from(from_name='判断是否执行', status=STATUS_FIND_NEXT_PLAN)
    @operation_node(name='查找候选计划')
    def find_next_plan(self) -> OperationRoundResult:
        """
        查找计划列表中的下一个候选计划

        找到后更新 self.current_plan；是否执行交给后续节点判断。
        """
        if self.temp_plan is not None:
            self.current_plan = self.temp_plan
            return self.round_success()

        # 检查是否所有计划都已完成
        if self.config.all_plan_finished():
            # 如果开启了循环模式且所有计划已完成，重置计划并继续
            if self.config.loop:
                self.last_tried_plan = None
                self.config.reset_plans()
            else:
                return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)

        candidate_plan = self.config.get_next_plan(self.last_tried_plan)
        if candidate_plan is None:
            return self.round_fail(ChargePlanApp.STATUS_NO_PLAN)

        self.current_plan = candidate_plan
        return self.round_success()

    @node_from(from_name='查找候选计划')
    @operation_node(name='判断是否执行')
    def check_before_transport(self) -> OperationRoundResult:
        if self.current_plan is self.temp_plan:
            return self.round_success()

        # 未知类型会返回 0，交给副本内流程继续判断真实消耗
        need_battery_charge = self.current_plan.estimated_charge_power
        if need_battery_charge <= 0 or self.battery_charge >= need_battery_charge:
            return self.round_success()

        if self._can_restore_charge(need_battery_charge - self.battery_charge):
            return self.round_success()

        if not self.config.skip_plan:
            return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)

        self.current_plan.skipped = True
        self.last_tried_plan = self.current_plan
        return self.round_success(ChargePlanApp.STATUS_FIND_NEXT_PLAN)

    def _can_restore_charge(self, required_charge: int) -> bool:
        if not self.config.is_restore_charge_enabled:
            return False

        restore_charge = self.config.restore_charge
        return (
            restore_charge in (
                RestoreChargeEnum.BACKUP_ONLY.value.value,
                RestoreChargeEnum.BOTH.value.value,
            )
            and self.backup_battery_charge >= required_charge
        ) or (
            restore_charge in (
                RestoreChargeEnum.ETHER_ONLY.value.value,
                RestoreChargeEnum.BOTH.value.value,
            )
            and self.ether_battery * 60 >= required_charge
        )

    @node_from(from_name='判断是否执行')
    @operation_node(name='传送')
    def transport(self) -> OperationRoundResult:
        # 使用已经在查找候选计划节点中设置好的 self.current_plan
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
        if self.current_plan is self.temp_plan:
            self.temp_plan = None
        return self.round_success()

    @node_from(from_name='实战模拟室', status=CombatSimulation.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='区域巡防', status=AreaPatrol.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='专业挑战室', status=ExpertChallenge.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='恶名狩猎', status=NotoriousHunt.STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='恶名狩猎', status=NotoriousHunt.STATUS_BLOCKED_BY_LEFT_TIMES)
    @node_from(from_name='实战模拟室', status=ChooseNextOrFinishAfterBattle.STATUS_AGENT_PLAN_FINISHED)
    @node_from(from_name='区域巡防', status=ChooseNextOrFinishAfterBattle.STATUS_AGENT_PLAN_FINISHED)
    @node_from(from_name='专业挑战室', status=ChooseNextOrFinishAfterBattle.STATUS_AGENT_PLAN_FINISHED)
    @node_from(from_name='恶名狩猎', status=ChooseNextOrFinishAfterBattle.STATUS_AGENT_PLAN_FINISHED)
    @node_from(from_name='传送', success=False, status='找不到 代理人方案培养')
    @operation_node(name='跳过或结束计划')
    def skip_plan_or_finish(self) -> OperationRoundResult:
        is_agent_plan = self.current_plan.is_agent_plan
        is_blocked_by_left_times = (
            self.previous_node.status == NotoriousHunt.STATUS_BLOCKED_BY_LEFT_TIMES
        )
        if self.config.skip_plan or is_agent_plan or is_blocked_by_left_times:
            # 标记当前计划为跳过，继续尝试下一个
            self.current_plan.skipped = True
            self.last_tried_plan = self.current_plan
            if self.current_plan is self.temp_plan:
                self.temp_plan = None
            return self.round_success(ChargePlanApp.STATUS_FIND_NEXT_PLAN)
        else:
            # 不跳过，直接结束本轮计划
            self.last_tried_plan = None
            if self.current_plan is self.temp_plan:
                self.temp_plan = None
            return self.round_success(ChargePlanApp.STATUS_ROUND_FINISHED)

    @node_from(from_name='跳过或结束计划', status=STATUS_ROUND_FINISHED)
    @node_from(from_name='查找候选计划', status=STATUS_ROUND_FINISHED)
    @node_from(from_name='查找候选计划', success=False)
    @node_from(from_name='判断是否执行', status=STATUS_ROUND_FINISHED)
    @node_notify(when=NotifyTiming.CURRENT_DONE, detail=True)
    @operation_node(name='返回大世界')
    def back_to_world(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        op_result = op.execute()
        return self.round_by_op_result(op_result, status=f'剩余电量 {self.battery_charge}')


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
