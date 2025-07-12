import time

import cv2
import difflib
import numpy as np
from typing import Optional, List, ClassVar

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import os_utils, cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.application.coffee.coffee_config import CoffeeChooseWay, CoffeeChallengeWay
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.compendium import Coffee
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.compendium.combat_simulation import CombatSimulation
from zzz_od.operation.compendium.expert_challenge import ExpertChallenge
from zzz_od.operation.compendium.routine_cleanup import RoutineCleanup
from zzz_od.operation.transport import Transport


class CoffeeApp(ZApplication):

    STATUS_EXTRA_COFFEE: ClassVar[str] = '不占用上限的咖啡'
    STATUS_WITHOUT_BENEFIT: ClassVar[str] = '没有增益的咖啡'

    def __init__(self, ctx: ZContext):
        """
        每天自动接收邮件奖励
        """
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='coffee',
            op_name=gt('咖啡店'),
            run_record=ctx.coffee_record,
            retry_in_od=True,  # 传送落地有可能会歪 重试
            need_notify=True,
        )

        self.chosen_coffee: Optional[Coffee] = None  # 选择的咖啡
        self.charge_plan: Optional[ChargePlanItem] = None  # 咖啡模拟生成的挑战计划
        self.had_coffee_list: set[str] = set()  # 已经喝过的咖啡

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        pass

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        op = Transport(self.ctx, '六分街', '咖啡店', wait_at_last=False)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送')
    @operation_node(name='等待大世界加载', node_max_retry_times=60)
    def wait_world(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '咖啡店', '点单')
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_area(screen, '大世界', '信息')
        if result.is_success:
            return self.round_success(result.status)

        return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='等待大世界加载')
    @operation_node(name='移动交互')
    def move_and_interact(self) -> OperationRoundResult:
        """
        传送之后 往前移动一下 方便交互
        :return:
        """
        self.ctx.controller.move_w(press=True, press_time=1, release=True)
        time.sleep(1)

        self.ctx.controller.interact(press=True, press_time=0.2, release=True)

        return self.round_success()

    @node_from(from_name='移动交互')
    @operation_node(name='等待咖啡店加载', node_max_retry_times=20)
    def wait_coffee_shop(self) -> OperationRoundResult:
        screen = self.screenshot()
        # 画面加载的时候，是滑动出现的，点单出现的时候，还未必能点击选中咖啡，因此要success_wait
        return self.round_by_find_area(screen, '咖啡店', '点单',
                                       success_wait=1, retry_wait=1)

    @node_from(from_name='等待大世界加载', status='点单')
    @node_from(from_name='等待咖啡店加载')
    @node_from(from_name='电量确认', status=STATUS_EXTRA_COFFEE)
    @operation_node(name='选择咖啡')
    def choose_coffee(self) -> OperationRoundResult:
        day = os_utils.get_current_day_of_week(self.ctx.game_account_config.game_refresh_hour_offset)
        to_choose_list = self._get_coffee_to_choose(day)

        screen = self.screenshot()
        # from one_dragon.utils import debug_utils
        # screen = debug_utils.get_debug_image('424905412-5c9df2d3-186d-4be5-a610-865553fd6adb')
        area = self.ctx.screen_loader.get_area('咖啡店', '咖啡列表')
        part = cv2_utils.crop_image_only(screen, area.rect)
        mask = cv2.inRange(part,
                           np.array([220, 220, 220], dtype=np.uint8),
                           np.array([255, 255, 255], dtype=np.uint8))
        to_ocr = cv2.bitwise_and(part, part, mask=cv2_utils.dilate(mask, 5))

        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)
        ocr_result_list: List[str] = []
        mrl_list: List[MatchResultList] = []
        for ocr_result, mrl in ocr_result_map.items():
            ocr_result_list.append(ocr_result)
            mrl_list.append(mrl)

        for lcs_percent in [0.8, 0.6, 0.4]:
            for coffee_name in to_choose_list:
                results = difflib.get_close_matches(gt(coffee_name, 'game'), ocr_result_list, n=1)
                if results is None or len(results) == 0:
                    continue

                if not str_utils.find_by_lcs(gt(coffee_name, 'game'), results[0], percent=lcs_percent):
                    continue

                # 对于浓淡二字特殊判断
                if coffee_name.find('浓') > -1 and results[0].find('浓') == -1:
                    continue
                if results[0].find('浓') > -1 and coffee_name.find('浓') == -1:
                    continue

                if coffee_name.find('淡') > -1 and results[0].find('淡') == -1:
                    continue
                if results[0].find('淡') > -1 and coffee_name.find('淡') == -1:
                    continue

                mrl = mrl_list[ocr_result_list.index(results[0])]
                self.chosen_coffee = self.ctx.compendium_service.name_2_coffee[coffee_name]
                time.sleep(0.5)  # 暂停半秒以防点不到咖啡
                self.ctx.controller.click(mrl.max.center + area.left_top + Point(0, -50))
                return self.round_success(self.chosen_coffee.coffee_name, wait=0.5)

        if day == 7:  # 目前只有星期日需要右滑找咖啡
            start = area.center
            end = start + Point(-200, 0)
            self.ctx.controller.drag_to(start=start, end=end)

        return self.round_retry(status='没找到目标咖啡', wait=1)

    def _get_coffee_to_choose(self, day: int) -> List[str]:
        """
        获取需要选择的咖啡名称列表
        :return:
        """
        to_choose_list = []

        for i in self.ctx.compendium_service.get_extra_coffee_list():
            if i.coffee_name in self.had_coffee_list:
                continue
            to_choose_list.append(i.coffee_name)

        if self.ctx.coffee_config.choose_way == CoffeeChooseWay.PLAN_PRIORITY.value.value:
            opt_coffee_list = self.ctx.compendium_service.coffee_schedule[day]

            self.ctx.charge_plan_config.reset_plans()
            # 先找还没有完成的计划
            for plan in self.ctx.charge_plan_config.plan_list:
                if plan.run_times >= plan.plan_times:
                    continue
                for coffee in opt_coffee_list:
                    if self._is_coffee_for_plan(coffee, plan):
                        to_choose_list.append(coffee.coffee_name)
                    break

            # 再找还已经完成的计划
            for plan in self.ctx.charge_plan_config.plan_list:
                if plan.run_times < plan.plan_times:
                    continue
                for coffee in opt_coffee_list:
                    if coffee.coffee_name in self.had_coffee_list:
                        continue
                    if self._is_coffee_for_plan(coffee, plan):
                        to_choose_list.append(coffee.coffee_name)
                    break

            # 没有符合的咖啡 就把兜底的咖啡加进来
            if len(to_choose_list) == 0:
                for coffee in opt_coffee_list:
                    if coffee.without_benefit:
                        to_choose_list.append(coffee.coffee_name)
                        break

        day_config_coffee = self.ctx.coffee_config.get_coffee_by_day(day)
        if day_config_coffee not in self.had_coffee_list:
            to_choose_list.append(day_config_coffee)

        return to_choose_list

    def _is_coffee_for_plan(self, coffee: Coffee, plan: ChargePlanItem) -> bool:
        """
        咖啡是否符合体力计划
        :param coffee:
        :param plan:
        :return:
        """
        if plan.category_name == '实战模拟室' and coffee.coffee_name == '浓缩咖啡':
            return True

        if coffee.without_benefit:
            return False

        if coffee.mission_type.mission_type_name != plan.mission_type_name:
            return False

        if coffee.mission is not None and coffee.mission.mission_name != plan.mission_name:
            return False

        return True

    @node_from(from_name='选择咖啡')
    @operation_node(name='点单')
    def order_coffee(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_and_click_area(screen, '咖啡店', '点单')
        if result.is_success:
            self.had_coffee_list.add(self.chosen_coffee.coffee_name)
            if self.chosen_coffee.extra:
                return self.round_success(status=CoffeeApp.STATUS_EXTRA_COFFEE, wait=1)
            elif self.chosen_coffee.without_benefit:
                return self.round_success(status=CoffeeApp.STATUS_WITHOUT_BENEFIT, wait=1)
            else:
                return self.round_success(wait=3)
        return self.round_retry(wait=1)

    @node_from(from_name='点单', status=STATUS_EXTRA_COFFEE)
    @operation_node(name='不占用点单确认')
    def extra_order_confirm(self) -> OperationRoundResult:
        screen = self.screenshot()
        result = self.round_by_find_and_click_area(screen, '咖啡店', '对话框确认')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '咖啡店', '不可贪杯确认')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        return self.round_retry(wait=1)

    @node_from(from_name='点单')
    @node_from(from_name='不占用点单确认')
    @operation_node(name='点单后跳过')
    def skip_after_order(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '咖啡店', '电量确认')
        if result.is_success:
            return self.round_success(result.status)

        # 这个点击很怪 需要多点几次
        result = self.round_by_find_and_click_area(screen, '咖啡店', '点单后跳过')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '咖啡店', '不可贪杯确认')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='点单后跳过')
    @operation_node(name='电量确认')
    def charge_confirm(self) -> OperationRoundResult:
        screen = self.screenshot()
        result = self.round_by_find_and_click_area(screen, '咖啡店', '电量确认')

        if result.is_success:
            if self.chosen_coffee.extra:
                return self.round_success(CoffeeApp.STATUS_EXTRA_COFFEE, wait=1)
            else:
                return self.round_success(wait=1)

        return self.round_retry(wait=1)

    @node_from(from_name='电量确认')
    @operation_node(name='选择前往')
    def choose_go(self) -> OperationRoundResult:
        if self.chosen_coffee.without_benefit:
            # 没有加成的
            return self.round_success('没有加成')

        screen = self.screenshot()

        if self.ctx.coffee_config.challenge_way == CoffeeChallengeWay.NONE.value.value:
            # 不挑战的
            return self.round_by_find_and_click_area(screen, '咖啡店', '对话框确认',
                                                     success_wait=1, retry_wait=1)

        if self.ctx.coffee_config.challenge_way == CoffeeChallengeWay.ONLY_PLAN.value.value:
            # 只挑战体力计划的
            in_plan = False
            for plan in self.ctx.charge_plan_config.plan_list:
                if self._is_coffee_for_plan(self.chosen_coffee, plan):
                    in_plan = True
                    break

            if not in_plan:
                return self.round_by_find_and_click_area(screen, '咖啡店', '对话框确认',
                                                         success_wait=1, retry_wait=1)

        return self.round_by_find_and_click_area(screen, '咖啡店', '对话框前往',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='选择前往', status='对话框前往')
    @operation_node(name='传送副本')
    def tp_mission(self) -> OperationRoundResult:
        if self.chosen_coffee.without_benefit:
            return self.round_fail('没有增益的咖啡')

        coffee_plan: Optional[ChargePlanItem] = None
        for plan in self.ctx.charge_plan_config.plan_list:
            if self._is_coffee_for_plan(self.chosen_coffee, plan):
                coffee_plan = plan
                break

        if coffee_plan is None:
            card_num = self.ctx.coffee_config.card_num
        else:
            card_num = coffee_plan.card_num

        self.charge_plan = ChargePlanItem(
            tab_name=self.chosen_coffee.tab.tab_name,
            category_name=self.chosen_coffee.category.category_name,
            mission_type_name=self.chosen_coffee.mission_type.mission_type_name,
            mission_name=None if self.chosen_coffee.mission is None else self.chosen_coffee.mission.mission_name,
            predefined_team_idx=self.ctx.coffee_config.predefined_team_idx,
            auto_battle_config=self.ctx.coffee_config.auto_battle,
            run_times=0,
            plan_times=1,
            card_num=card_num
        )

        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('咖啡店', '对话框确认')
        result = self.round_by_ocr_and_click(screen, '确认', area=area)

        if result.is_success:
            return self.round_success(self.charge_plan.category_name, wait=5)
        else:
            return self.round_retry(result.status, wait=1)

    @node_from(from_name='传送副本', status='实战模拟室')
    @operation_node(name='实战模拟室')
    def combat_simulation(self) -> OperationRoundResult:
        op = CombatSimulation(self.ctx, self.charge_plan)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送副本', status='定期清剿')
    @operation_node(name='定期清剿')
    def routine_cleanup(self) -> OperationRoundResult:
        op = RoutineCleanup(self.ctx, self.charge_plan)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='传送副本', status='专业挑战室')
    @operation_node(name='专业挑战室')
    def expert_challenge(self) -> OperationRoundResult:
        op = ExpertChallenge(self.ctx, self.charge_plan)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='不占用点单确认', status='不可贪杯确认')  # 已经喝过了
    @node_from(from_name='点单后跳过', status='不可贪杯确认')  # 已经喝过了
    @node_from(from_name='选择前往', status='对话框确认')
    @node_from(from_name='选择前往', status='没有加成')
    @node_from(from_name='实战模拟室')
    @node_from(from_name='定期清剿')
    @node_from(from_name='专业挑战室')
    @operation_node(name='返回大世界')
    def back_to_world(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='返回大世界')
    @operation_node(name='结束后运行体力计划')
    def charge_plan_afterwards(self) -> OperationRoundResult:
        if self.ctx.coffee_config.run_charge_plan_afterwards:
            op = ChargePlanApp(self.ctx)
            op.init_context_before_start = False
            op.stop_context_after_stop = False
            return self.round_by_op_result(op.execute())
        else:
            return self.round_success('无需运行')


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    app = CoffeeApp(ctx)
    app.chosen_coffee = ctx.compendium_service.name_2_coffee['汀曼特调']
    app._init_before_execute()
    # app.tp_mission()
    # app.had_coffee_list.add('沙罗特调（浓）')
    app.choose_coffee()
    # app.execute()


if __name__ == '__main__':
    __debug()


