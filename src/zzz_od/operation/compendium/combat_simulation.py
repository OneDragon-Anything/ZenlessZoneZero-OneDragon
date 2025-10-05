import time
from concurrent.futures import Future
from typing import Optional, ClassVar, Tuple

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem, CardNumEnum, ChargePlanConfig
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.challenge_mission.check_next_after_battle import ChooseNextOrFinishAfterBattle
from zzz_od.operation.challenge_mission.exit_in_battle import ExitInBattle
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam
from zzz_od.operation.deploy import Deploy
from zzz_od.operation.restore_charge import RestoreCharge
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum


class CombatSimulation(ZOperation):

    STATUS_NEED_TYPE: ClassVar[str] = '需选择类型'
    STATUS_CHOOSE_SUCCESS: ClassVar[str] = '选择成功'
    STATUS_CHOOSE_FAIL: ClassVar[str] = '选择失败'
    STATUS_CHARGE_NOT_ENOUGH: ClassVar[str] = '电量不足'
    STATUS_CHARGE_ENOUGH: ClassVar[str] = '电量充足'
    STATUS_FIGHT_TIMEOUT: ClassVar[str] = '战斗超时'

    def __init__(self, ctx: ZContext, plan: ChargePlanItem,
                 can_run_times: Optional[int] = None,
                 need_check_power: bool = False):
        """
        使用快捷手册传送后
        用这个进行挑战
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name='%s %s' % (
                gt('实战模拟室', 'game'),
                gt(plan.mission_name, 'game')
            )
        )
        self.config: Optional[ChargePlanConfig] = self.ctx.run_context.get_config(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.plan: ChargePlanItem = plan
        self.need_check_power: bool = need_check_power
        self.can_run_times: int = can_run_times
        self.charge_left: Optional[int] = None
        self.charge_need: Optional[int] = None
        self.scroll_count: int = 0  # 滑动次数计数器

        self.auto_op: Optional[AutoBattleOperator] = None
        self.async_init_future: Optional[Future[Tuple[bool, str]]] = None  # 初始化自动战斗的future

    @operation_node(name='异步初始化自动战斗')
    def async_init_auto_op(self) -> OperationRoundResult:
        """
        暂时不需要异步加载
        """
        if self.plan.predefined_team_idx == -1:
            auto_battle = self.plan.auto_battle_config
        else:
            team_list = self.ctx.team_config.team_list
            auto_battle = team_list[self.plan.predefined_team_idx].auto_battle

        self.async_init_future = auto_battle_utils.load_auto_op_async(self, 'auto_battle', auto_battle)
        return self.round_success(auto_battle)

    @node_from(from_name='异步初始化自动战斗')
    @operation_node(name='等待入口加载', is_start_node=True, node_max_retry_times=60)
    def wait_entry_load(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '实战模拟室', '挑战等级')
        if result.is_success:
            return self.round_success(self.plan.mission_type_name)

        if self.is_in_category_screen(self.last_screenshot):
            return self.round_success(CombatSimulation.STATUS_NEED_TYPE)

        return self.round_retry(wait=1)

    @node_from(from_name='等待入口加载', status='自定义模板')
    @operation_node(name='自定义模版的返回')
    def back_for_div(self) -> OperationRoundResult:
        if self.is_in_category_screen(self.last_screenshot):
            return self.round_success()

        result = self.round_by_click_area('菜单', '返回')
        if result.is_success:
            return self.round_retry('尝试返回副本类型列表' ,wait=1)
        else:
            return self.round_retry(result.status, wait=1)

    def is_in_category_screen(self, screen) -> bool:
        """
        是否在选择类别的画面
        :param screen: 游戏画面
        :return:
        """
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        category = self.ctx.compendium_service.get_category_data('训练', '实战模拟室')
        if category is None:
            return False
        target_word_list: list[str] = [gt(i.mission_type_name, 'game') for i in category.mission_type_list]
        match_type_cnt: int = 0
        for ocr_result in ocr_result_map.keys():
            match_idx: int = str_utils.find_best_match_by_difflib(ocr_result, target_word_list)
            if match_idx is not None and match_idx >= 0:
                match_type_cnt += 1
        return match_type_cnt >= 3

    @node_from(from_name='等待入口加载', status=STATUS_NEED_TYPE)
    @node_from(from_name='自定义模版的返回')
    @operation_node(name='选择类型')
    def choose_mission_type(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('实战模拟室', '副本类型列表')
        return self.round_by_ocr_and_click(self.last_screenshot, self.plan.mission_type_name, area=area,
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='等待入口加载')
    @node_from(from_name='选择类型')
    @operation_node(name='选择副本')
    def choose_mission(self) -> OperationRoundResult:

        # 滑动次数大于5则返回失败
        if self.scroll_count > 5:
            self.scroll_count = 0
            return self.round_success(status=CombatSimulation.STATUS_CHOOSE_FAIL)

        if self.plan.mission_name == '代理人方案培养':
            target_point: Optional[Point] = None

            area = self.ctx.screen_loader.get_area('实战模拟室', '副本名称列表顶部')
            part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)

            # 直接获取点击位置
            click_pos = cv2_utils.find_character_avatar_center_with_offset(
                part,
                area_offset=(area.left_top.x, area.left_top.y),
                click_offset=(0, 80),  # 向下偏移80像素，用于点击头像下方的区域
                min_area=800
            )

            if click_pos:
                target_point = Point(click_pos[0], click_pos[1])
                log.info(f'找到代理人目标，点击位置: {target_point}')

            if target_point is None:
                start = area.center
                end = start + Point(-400, 0)
                self.ctx.controller.drag_to(start=start, end=end)
                self.scroll_count += 1
                return self.round_retry(status='找不到 %s' % self.plan.mission_name, wait=1)

        else:
            area = self.ctx.screen_loader.get_area('实战模拟室', '副本名称列表')
            part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)

            target_point: Optional[Point] = None
            ocr_result_map = self.ctx.ocr.run_ocr(part)
            ocr_word_list = []
            mrl_list = []
            for ocr_result, mrl in ocr_result_map.items():
                ocr_word_list.append(ocr_result)
                mrl_list.append(mrl)

            # 有副本名字太接近 需要额外区分 例如 '击破演练', '命破演练'
            cutoff = 0.8
            idx = str_utils.find_best_match_by_difflib(gt(self.plan.mission_name, 'game'), ocr_word_list, cutoff=cutoff)

            if idx is not None and idx >= 0:
                mrl = mrl_list[idx]
                target_point = area.left_top + mrl.max + Point(0, 50)
            else:
                mission_list = self.ctx.compendium_service.get_mission_list_data(self.plan.tab_name, self.plan.category_name, self.plan.mission_type_name)
                mission_name_list = [i.mission_name for i in mission_list]
                is_after: bool = str_utils.is_target_after_ocr_list(self.plan.mission_name, mission_name_list, ocr_word_list, cutoff=cutoff)

                area = self.ctx.screen_loader.get_area('实战模拟室', '副本名称列表')
                start = area.center
                end = start + Point(400 * (-1 if is_after else 1), 0)
                self.ctx.controller.drag_to(start=start, end=end)
                self.scroll_count += 1
                return self.round_retry(status='找不到 %s' % self.plan.mission_name, wait=1)

        self.ctx.controller.click(target_point)
        return self.round_success(status=CombatSimulation.STATUS_CHOOSE_SUCCESS, wait=1)

    @node_from(from_name='选择副本', status=STATUS_CHOOSE_SUCCESS)
    @operation_node(name='进入选择数量')
    def click_card(self) -> OperationRoundResult:
        if self.plan.card_num == CardNumEnum.DEFAULT.value.value:
            return self.round_success(self.plan.card_num)
        else:
            return self.round_by_click_area('实战模拟室', '外层-卡片1',
                                            success_wait=1, retry_wait=1)

    @node_from(from_name='进入选择数量')
    @operation_node(name='选择数量')
    def choose_card_num(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '实战模拟室', '保存方案')
        if not result.is_success:
            return self.round_retry(result.status, wait=1)

        for i in range(1, 6):
            log.info('开始取消已选择数量 %d', i)
            self.round_by_click_area('实战模拟室', '内层-已选择卡片1')
            time.sleep(0.5)
        for i in range(1, int(self.plan.card_num) + 1):
            log.info('开始选择数量 %d', i)
            self.round_by_click_area('实战模拟室', '内层-卡片1')
            time.sleep(0.5)

        return self.round_by_find_and_click_area(self.last_screenshot, '实战模拟室', '保存方案',
                                                 success_wait=2, retry_wait=1)

    @node_from(from_name='进入选择数量', status=CardNumEnum.DEFAULT.value.value)
    @node_from(from_name='选择数量')
    @operation_node(name='识别电量')
    def check_charge(self) -> OperationRoundResult:
        if not self.need_check_power:
            if self.can_run_times > 0:
                return self.round_success(CombatSimulation.STATUS_CHARGE_ENOUGH)
            else:
                return self.round_success(CombatSimulation.STATUS_CHARGE_NOT_ENOUGH)

        area = self.ctx.screen_loader.get_area('实战模拟室', '剩余电量')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        self.charge_left = str_utils.get_positive_digits(ocr_result, None)
        if self.charge_left is None:
            return self.round_retry(status='识别 %s 失败' % '剩余电量', wait=1)

        area = self.ctx.screen_loader.get_area('实战模拟室', '需要电量')
        part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)
        self.charge_need = str_utils.get_positive_digits(ocr_result, None)
        if self.charge_need is None:
            return self.round_retry(status='识别 %s 失败' % '需要电量', wait=1)

        log.info('所需电量 %d 剩余电量 %d', self.charge_need, self.charge_left)
        if self.charge_need > self.charge_left:
            return self.round_success(CombatSimulation.STATUS_CHARGE_NOT_ENOUGH)

        self.can_run_times = self.charge_left // self.charge_need
        max_need_run_times = self.plan.plan_times - self.plan.run_times

        if self.can_run_times > max_need_run_times:
            self.can_run_times = max_need_run_times

        return self.round_success(CombatSimulation.STATUS_CHARGE_ENOUGH)

    @node_from(from_name='识别电量', status=STATUS_CHARGE_NOT_ENOUGH)
    @node_from(from_name='下一步', status=STATUS_CHARGE_NOT_ENOUGH)
    @operation_node(name='恢复电量')
    def restore_charge(self) -> OperationRoundResult:
        if not self.config.is_restore_charge_enabled:
            return self.round_success(CombatSimulation.STATUS_CHARGE_NOT_ENOUGH)
        op = RestoreCharge(self.ctx)
        result = self.round_by_op_result(op.execute())
        return result if result.is_success else self.round_success(CombatSimulation.STATUS_CHARGE_NOT_ENOUGH)

    @node_from(from_name='识别电量', status=STATUS_CHARGE_ENOUGH)
    @node_from(from_name='恢复电量', status='恢复电量成功')
    @operation_node(name='下一步', node_max_retry_times=10)  # 部分机器加载较慢 延长出战的识别时间
    def click_next(self) -> OperationRoundResult:
        # 防止前面电量识别错误
        result = self.round_by_find_area(self.last_screenshot, '实战模拟室', '恢复电量')
        if result.is_success:
            return self.round_success(status=CombatSimulation.STATUS_CHARGE_NOT_ENOUGH)

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
        if self.async_init_future is not None:
            try:
                success, msg = self.async_init_future.result(60)
                if not success:
                    return self.round_fail(msg)
                else:
                    return self.round_success()
            except Exception as e:
                return self.round_fail('自动战斗初始化失败')
        else:
            if self.plan.predefined_team_idx == -1:
                auto_battle = self.plan.auto_battle_config
            else:
                team_list = self.ctx.team_config.team_list
                auto_battle = team_list[self.plan.predefined_team_idx].auto_battle

            return auto_battle_utils.load_auto_op(self, 'auto_battle', auto_battle)

    @node_from(from_name='加载自动战斗指令')
    @operation_node(name='等待战斗画面加载', node_max_retry_times=60)
    def wait_battle_screen(self) -> OperationRoundResult:
        return self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击', retry_wait_round=1)

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='向前移动准备战斗')
    def move_to_battle(self) -> OperationRoundResult:
        self.ctx.controller.move_w(press=True, press_time=1, release=True)
        return self.round_success()

    @node_from(from_name='向前移动准备战斗')
    @operation_node(name='开始自动战斗')
    def start_auto_op(self) -> OperationRoundResult:
        self.auto_op.start_running_async()
        return self.round_success()

    @node_from(from_name='开始自动战斗')
    @operation_node(name='自动战斗', mute=True, timeout_seconds=600)
    def auto_battle(self) -> OperationRoundResult:
        if self.auto_op.auto_battle_context.last_check_end_result is not None:
            auto_battle_utils.stop_running(self.auto_op)
            return self.round_success(status=self.auto_op.auto_battle_context.last_check_end_result)

        self.auto_op.auto_battle_context.check_battle_state(
            self.last_screenshot, self.last_screenshot_time,
            check_battle_end_normal_result=True)

        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='自动战斗')
    @operation_node(name='战斗结束')
    def after_battle(self) -> OperationRoundResult:
        self.can_run_times -= 1
        self.config.add_plan_run_times(self.plan)
        return self.round_success()

    @node_from(from_name='战斗结束')
    @operation_node(name='判断下一次')
    def check_next(self) -> OperationRoundResult:
        op = ChooseNextOrFinishAfterBattle(self.ctx, self.plan.plan_times > self.plan.run_times)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别电量', success=False)
    @operation_node(name='识别电量失败')
    def check_charge_fail(self) -> OperationRoundResult:
        return self.round_success(CombatSimulation.STATUS_CHARGE_NOT_ENOUGH)

    @node_from(from_name='自动战斗', success=False, status=Operation.STATUS_TIMEOUT)
    @operation_node(name='战斗超时')
    def battle_timeout(self) -> OperationRoundResult:
        auto_battle_utils.stop_running(self.auto_op)
        op = ExitInBattle(self.ctx, '画面-通用', '左上角-街区')
        result = self.round_by_op_result(op.execute())
        if result.is_success:
            return self.round_fail(status=CombatSimulation.STATUS_FIGHT_TIMEOUT)
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
        if self.auto_op is not None:
            self.auto_op.stop_running()

    def handle_resume(self):
        auto_battle_utils.resume_running(self.auto_op)

    def after_operation_done(self, result: OperationResult):
        ZOperation.after_operation_done(self, result)
        if self.auto_op is not None:
            self.auto_op.dispose()
            self.auto_op = None


def __debug_coffee():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
    chosen_coffee = ctx.compendium_service.name_2_coffee['麦草拿提']
    charge_plan = ChargePlanItem(
        tab_name=chosen_coffee.tab.tab_name,
        category_name=chosen_coffee.category.category_name,
        mission_type_name=chosen_coffee.mission_type.mission_type_name,
        mission_name=None if chosen_coffee.mission is None else chosen_coffee.mission.mission_name,
        auto_battle_config='全配队通用',
        run_times=0,
        plan_times=1
    )
    op = CombatSimulation(ctx, charge_plan)
    op.can_run_times = 1
    op.execute()

def __debug_charge():
    """
    测试电量识别
    @return:
    """
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('_1752673754384')
    area = ctx.screen_loader.get_area('实战模拟室', '剩余电量')
    part = cv2_utils.crop_image_only(screen, area.rect)
    cv2_utils.show_image(part, wait=0)
    ocr_result = ctx.ocr.run_ocr_single_line(part)
    print(ocr_result)

def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.run_context.start_running()
    charge_plan = ChargePlanItem(
        tab_name='训练',
        category_name='实战模拟室',
        mission_type_name='代理人晋升',
        mission_name='防护演练',
        run_times=0,
        plan_times=1,
        predefined_team_idx=-1,
        auto_battle_config='全配对通用',
    )
    op = CombatSimulation(ctx, charge_plan)
    op.can_run_times = 1
    op.execute()


if __name__ == '__main__':
    __debug()
