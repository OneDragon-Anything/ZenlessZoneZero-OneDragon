import time
from typing import ClassVar

import cv2
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_notify import NotifyTiming, node_notify
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import (
    CardNumEnum,
    ChargePlanConfig,
    ChargePlanItem,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.challenge_mission.check_next_after_battle import (
    ChooseNextOrFinishAfterBattle,
)
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
    STATUS_FIGHT_TIMEOUT: ClassVar[str] = '战斗超时'

    def __init__(self, ctx: ZContext, plan: ChargePlanItem):
        """
        使用快捷手册传送后
        用这个进行挑战
        :param ctx:
        """
        ZOperation.__init__(
            self, ctx,
            op_name='{} {}'.format(
                gt('实战模拟室', 'game'),
                gt(plan.mission_name, 'game')
            )
        )
        self.config: ChargePlanConfig = self.ctx.run_context.get_config(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.plan: ChargePlanItem = plan
        self.scroll_count: int = 0  # 滑动次数计数器

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
        for ocr_result in ocr_result_map:
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

        # 滑动次数大于10则返回失败
        if self.scroll_count > 10:
            self.scroll_count = 0
            return self.round_fail(status=CombatSimulation.STATUS_CHOOSE_FAIL)

        if self.plan.is_agent_plan:
            target_point: Point | None = None

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
                start = area.center + Point(-100, 0)
                end = start + Point(-400, 0)
                self.ctx.controller.drag_to(start=start, end=end)
                self.scroll_count += 1
                return self.round_retry(status=f'找不到 {self.plan.mission_name}', wait=1)

        else:
            area = self.ctx.screen_loader.get_area('实战模拟室', '副本名称列表')

            target_point: Point | None = None
            ocr_result_map = self.ctx.ocr.crop_and_run_ocr(self.last_screenshot, area.rect)
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
                return self.round_retry(status=f'找不到 {self.plan.mission_name}', wait=1)

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
    @node_from(from_name='恢复电量', status=RestoreCharge.STATUS_RESTORE_SUCCESS)
    @operation_node(name='下一步', node_max_retry_times=10)  # 部分机器加载较慢 延长出战的识别时间
    def click_next(self) -> OperationRoundResult:
        # 防止前面电量识别错误
        result = self.round_by_find_area(self.last_screenshot, '恢复电量', '标题-恢复电量')
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

    @node_from(from_name='下一步', status=STATUS_CHARGE_NOT_ENOUGH)
    @operation_node(name='恢复电量')
    def restore_charge(self) -> OperationRoundResult:
        if not self.config.is_restore_charge_enabled:
            return self.round_success(CombatSimulation.STATUS_CHARGE_NOT_ENOUGH)
        op = RestoreCharge(self.ctx)
        return self.round_by_op_result(op.execute())

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
        return self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击', retry_wait_round=1)

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='向前移动准备战斗')
    def move_to_battle(self) -> OperationRoundResult:
        self.ctx.controller.move_w(press=True, press_time=1, release=True)
        return self.round_success()

    @node_from(from_name='向前移动准备战斗')
    @operation_node(name='开始自动战斗')
    def start_auto_op(self) -> OperationRoundResult:
        self.ctx.auto_battle_context.start_auto_battle()
        return self.round_success()

    @node_from(from_name='开始自动战斗')
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

    @node_from(from_name='记录材料')
    @operation_node(name='判断下一次')
    def check_next(self) -> OperationRoundResult:
        op = ChooseNextOrFinishAfterBattle(
            self.ctx,
            not self.plan.is_finished,
            is_agent_plan=self.plan.is_agent_plan,
        )
        return self.round_by_op_result(op.execute())

    @staticmethod
    def _classify_reward_rarity(
        reward_part: MatLike,
        quantity_match: MatchResult,
    ) -> int | None:
        """按数量上方图标底色判断 A、B、C 级材料，返回 0、1、2。"""
        center_x = quantity_match.x + quantity_match.w // 2
        sample_bottom = max(0, quantity_match.y - 3)
        sample_rect = Rect(
            max(0, center_x - 25),
            max(0, sample_bottom - 18),
            min(reward_part.shape[1], center_x + 25),
            sample_bottom,
        )
        sample = cv2_utils.crop_image_only(reward_part, sample_rect)
        if sample.size == 0:
            return None

        # 控制器截图与 cv2_utils.read_image 都使用 RGB，不能按 OpenCV 默认的 BGR 转换。
        hsv = cv2.cvtColor(sample, cv2.COLOR_RGB2HSV)
        color_ranges = (
            ((125, 100, 80), (179, 255, 255)),  # A 级，紫色
            ((80, 100, 80), (124, 255, 255)),  # B 级，蓝色
            ((20, 100, 80), (49, 255, 255)),  # C 级，绿色
        )
        color_counts = [
            cv2.countNonZero(cv2.inRange(hsv, lower, upper))
            for lower, upper in color_ranges
        ]
        rarity_idx = max(range(len(color_counts)), key=color_counts.__getitem__)
        if color_counts[rarity_idx] < 10:
            return None
        return rarity_idx

    def read_material_reward_counts(
        self,
        screen: MatLike,
        material_names: tuple[str, ...],
    ) -> dict[str, int] | None:
        """读取结算页奖励格子的数量，并按材料品质合并同类奖励。"""
        if not material_names:
            return None

        reward_area = self.ctx.screen_loader.get_area(
            '战斗画面',
            '战斗结果-奖励',
        )
        reward_part = cv2_utils.crop_image_only(screen, reward_area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(reward_part)
        quantity_matches: list[tuple[int, MatchResult]] = []
        for text, match_result_list in ocr_result_map.items():
            stripped_text = text.strip()
            if not stripped_text.isdigit():
                continue
            quantity = str_utils.get_positive_digits(stripped_text, None)
            if quantity is None or quantity <= 0:
                continue
            for match_result in match_result_list:
                quantity_matches.append((quantity, match_result))

        if not quantity_matches:
            log.warning('结算页奖励数量识别失败 OCR=%s', list(ocr_result_map))
            return None

        if len(material_names) == 1:
            return {material_names[0]: sum(item[0] for item in quantity_matches)}

        result: dict[str, int] = {}
        for quantity, quantity_match in quantity_matches:
            rarity_idx = self._classify_reward_rarity(
                reward_part,
                quantity_match,
            )
            if rarity_idx is None or rarity_idx >= len(material_names):
                log.warning(
                    '结算页材料品质识别失败 数量=%d 位置=(%d,%d)',
                    quantity,
                    quantity_match.x,
                    quantity_match.y,
                )
                return None
            material_name = material_names[rarity_idx]
            result[material_name] = result.get(material_name, 0) + quantity
        return result

    @node_from(from_name='战斗结束')
    @operation_node(name='记录材料', node_max_retry_times=3)
    def record_material_rewards(self) -> OperationRoundResult:
        """按材料数量运行时在点击结算按钮前记录本场奖励。"""
        if not self.plan.is_material_count_plan:
            return self.round_success('无需记录材料')

        material_options = self.ctx.compendium_service.get_charge_plan_material_list(
            self.plan.category_name,
            self.plan.mission_type_name,
            self.plan.mission_name,
        )
        material_names = tuple(option.value for option in material_options)
        if self.plan.target_material_name not in material_names:
            return self.round_fail(
                f'目标材料不属于当前副本 {self.plan.target_material_name}'
            )

        material_counts = self.read_material_reward_counts(
            self.last_screenshot,
            material_names,
        )
        if material_counts is None:
            return self.round_retry('材料数量识别失败', wait=1)
        if not self.config.add_plan_material_counts(self.plan, material_counts):
            return self.round_fail('未找到对应的体力计划')

        log.info(
            '材料进度 %s %d/%d 本场=%s',
            self.plan.target_material_name,
            self.plan.current_material_count,
            self.plan.target_material_count,
            material_counts,
        )
        return self.round_success(
            f'材料进度 {self.plan.current_material_count}/{self.plan.target_material_count}'
        )

    @node_from(from_name='自动战斗', success=False, status=Operation.STATUS_TIMEOUT)
    @operation_node(name='战斗超时')
    def battle_timeout(self) -> OperationRoundResult:
        self.ctx.auto_battle_context.stop_auto_battle()
        op = ExitInBattle(self.ctx, '画面-通用', '左上角-区域')
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
        self.ctx.auto_battle_context.stop_auto_battle()

    def handle_resume(self):
        if self.current_node.node is not None and self.current_node.node.cn == '自动战斗':
            self.ctx.auto_battle_context.resume_auto_battle()


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
    op.execute()


if __name__ == '__main__':
    __debug()
