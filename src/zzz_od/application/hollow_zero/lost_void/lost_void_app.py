import time
from typing import ClassVar, Optional

import cv2

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.lost_void import lost_void_const
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidRegionType,
)
from zzz_od.application.hollow_zero.lost_void.lost_void_config import LostVoidConfig
from zzz_od.application.hollow_zero.lost_void.lost_void_run_record import (
    LostVoidRunRecord,
)
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_run_level import (
    LostVoidRunLevel,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent, AgentEnum
from zzz_od.game_data.compendium import CompendiumMissionType
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam
from zzz_od.operation.compendium.compendium_choose_category import (
    CompendiumChooseCategory,
)
from zzz_od.operation.compendium.compendium_choose_mission_type import (
    CompendiumChooseMissionType,
)
from zzz_od.operation.deploy import Deploy


class LostVoidApp(ZApplication):

    STATUS_ENOUGH_TIMES: ClassVar[str] = '完成通关次数'
    STATUS_AGAIN: ClassVar[str] = '继续挑战'

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=lost_void_const.APP_ID,
            op_name=lost_void_const.APP_NAME,
            need_notify=True,
        )
        self.config: Optional[LostVoidConfig] = self.ctx.run_context.get_config(
            app_id=lost_void_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self.run_record: Optional[LostVoidRunRecord] = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=lost_void_const.APP_ID,
        )

        self.next_region_type: LostVoidRegionType = LostVoidRegionType.ENTRY  # 下一个区域的类型
        self.priority_agent_list: list[Agent] = []  # 优先选择的代理人列表

        self.use_priority_agent: bool = False  # 本次挑战是否使用了UP代理人

    @operation_node(name='初始化加载', is_start_node=True)
    def init_for_lost_void(self) -> OperationRoundResult:
        if self.run_record.is_finished_by_day():
            return self.round_success(LostVoidApp.STATUS_ENOUGH_TIMES)

        try:
            # 这里会加载迷失之洞的数据 识别模型 和自动战斗配置
            self.ctx.lost_void.init_before_run()
        except Exception:
            return self.round_fail('初始化失败')
        return self.round_success(LostVoidApp.STATUS_AGAIN)

    @node_from(from_name='初始化加载', status=STATUS_AGAIN)
    @operation_node(name='识别初始画面')
    def check_initial_screen(self) -> OperationRoundResult:
        # 特殊兼容 在挑战区域开始
        result = self.round_by_find_and_click_area(self.last_screenshot, '迷失之地-大世界', '按钮-挑战-确认')
        if result.is_success:
            self.next_region_type = LostVoidRegionType.CHANLLENGE_TIME_TRAIL
            return self.round_wait(result.status, wait=1)

        mission_name = self.config.mission_name
        screen_name, can_go = self.check_screen_with_can_go(self.last_screenshot, f'迷失之地-{mission_name}')
        if screen_name is None:
            return self.round_retry(Operation.STATUS_SCREEN_UNKNOWN, wait=0.5)

        if screen_name == '迷失之地-大世界':
            return self.round_success('迷失之地-大世界')

        if can_go or screen_name == f'迷失之地-{mission_name}':
            return self.round_success('可前往副本画面')

        can_go = self.check_current_can_go('快捷手册-作战')
        if can_go:
            return self.round_success('可前往快捷手册')

        return self.round_retry('无法前往目标画面', wait=0.5)

    @node_from(from_name='识别初始画面', status=Operation.STATUS_SCREEN_UNKNOWN)
    @node_from(from_name='识别初始画面', status='无法前往目标画面')
    @operation_node(name='开始前返回大世界')
    def back_at_first(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别初始画面', status='可前往快捷手册')
    @node_from(from_name='开始前返回大世界')
    @operation_node(name='前往快捷手册')
    def goto_compendium(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='快捷手册-作战')

    @node_from(from_name='前往快捷手册')
    @operation_node(name='选择零号空洞')
    def choose_hollow_zero(self) -> OperationRoundResult:
        op = CompendiumChooseCategory(self.ctx, '零号空洞')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='选择零号空洞')
    @operation_node(name='选择迷失之地')
    def choose_lost_void(self) -> OperationRoundResult:
        mission_type: CompendiumMissionType = self.ctx.compendium_service.get_mission_type_data('作战', '零号空洞', '迷失之地')
        op = CompendiumChooseMissionType(self.ctx, mission_type)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别初始画面', status='可前往副本画面')
    @node_from(from_name='选择迷失之地')
    @node_from(from_name='通关后处理', status=STATUS_AGAIN)
    @operation_node(name='前往副本画面', node_max_retry_times=60)
    def goto_mission_screen(self) -> OperationRoundResult:
        mission_name = self.config.mission_name
        return self.round_by_goto_screen(screen_name=f'迷失之地-{mission_name}')

    @node_from(from_name='前往副本画面')
    @operation_node(name='副本画面识别')
    def check_for_mission(self) -> OperationRoundResult:
        """
        针对不同的副本类型 进行对应的所需识别
        :return:
        """
        mission_name = self.config.mission_name

        # 如果是特遣调查 则额外识别当期UP角色
        if mission_name == '特遣调查':
            match_agent_list: list[tuple[MatchResult, Agent]] = []

            area = self.ctx.screen_loader.get_area('迷失之地-特遣调查', '区域-代理人头像')
            part = cv2_utils.crop_image_only(self.last_screenshot, area.rect)
            source_kp, source_desc = cv2_utils.feature_detect_and_compute(part)
            for agent_enum in AgentEnum:
                agent: Agent = agent_enum.value
                for template_id in agent.template_id_list:
                    template = self.ctx.template_loader.get_template('predefined_team', f'avatar_{template_id}')
                    if template is None:
                        continue
                    template_kp, template_desc = template.features
                    mr = cv2_utils.feature_match_for_one(
                        source_kp, source_desc, template_kp, template_desc,
                        template_width=template.raw.shape[1], template_height=template.raw.shape[0],
                        knn_distance_percent=0.5
                    )
                    if mr is None:
                        continue

                    match_agent_list.append((mr, agent))

            # 从左往右排序
            match_agent_list.sort(key=lambda x: x[0].left_top.x)
            self.priority_agent_list = [x[1] for x in match_agent_list]

            display_name: str = ', '.join([i.agent_name for i in self.priority_agent_list])
            log.info(f'当前识别UP代理人列表: [{display_name}]')

            if len(self.priority_agent_list) > 0:
                return self.round_success()
            else:
                return self.round_retry(status='未识别UP代理人', wait=1)
        else:
            return self.round_success()

    @node_from(from_name='副本画面识别')
    @operation_node(name='打开调查战略列表')
    def open_strategy_list(self) -> OperationRoundResult:
        return self.round_by_click_area('迷失之地-战线肃清', '按钮-调查战略',
                                        success_wait=1, retry_wait=1)


    @node_from(from_name='打开调查战略列表')
    @operation_node(name='选择调查战略')
    def choose_strategy(self) -> OperationRoundResult:
        current_screen_name = self.check_and_update_current_screen(
            self.last_screenshot, screen_name_list=['迷失之地-战线肃清', '迷失之地-特遣调查']
        )
        if current_screen_name is not None:
            return self.round_success(current_screen_name)

        # [DEBUG] 打印关键决策参数
        config = self.ctx.lost_void.challenge_config
        log.debug(f"【决策检查】 追新模式: {config.chase_new_mode}, "
                  f"当前挑战配置: {config.module_name}, "
                  f"预设调查战略: {config.investigation_strategy}")

        # 追新模式逻辑
        if config.chase_new_mode:
            return self._choose_strategy_by_chase_new_mode()
        # 原有逻辑
        else:
            return self._choose_strategy_by_ocr()

    def _choose_strategy_by_chase_new_mode(self) -> OperationRoundResult:
        """
        追新模式下的选择逻辑
        """
        swipe_attempts = 0
        MAX_SWIPES = 3

        while swipe_attempts < MAX_SWIPES:
            log.debug("【追新模式】 开始执行CV流水线分析...")
            frame_context = self.ctx.cv_service.run_pipeline('调查战略等级圈圈', self.last_screenshot)
            digit_context = self.ctx.cv_service.run_pipeline('调查战略等级分析', self.last_screenshot)

            if not frame_context.is_success or not frame_context.contours:
                log.debug("【追新模式】 未找到任何战略外框，执行滑动...")
                self._swipe_strategy_list()
                swipe_attempts += 1
                continue

            target_contour_to_click = None
            log.debug(f"【追新模式】 找到 {len(frame_context.contours)} 个战略外框，"
                      f"{len(digit_context.contours) if digit_context.is_success and digit_context.contours else 0} 个等级数字。开始匹配...")
            for frame_contour in frame_context.contours:
                frame_rect = cv2.boundingRect(frame_contour)
                found_digit_contour = None

                if digit_context.is_success and digit_context.contours:
                    for digit_contour in digit_context.contours:
                        M = cv2.moments(digit_contour)
                        if M["m00"] == 0: continue
                        center_x = int(M["m10"] / M["m00"])
                        center_y = int(M["m01"] / M["m00"])

                        if (frame_rect[0] < center_x < frame_rect[0] + frame_rect[2] and
                                frame_rect[1] < center_y < frame_rect[1] + frame_rect[3]):
                            found_digit_contour = digit_contour
                            break

                if found_digit_contour is None:
                    log.debug("【追新模式】 找到一个未满级/无等级目标，准备点击。")
                    target_contour_to_click = frame_contour
                    break
            
            if target_contour_to_click is not None:
                M = cv2.moments(target_contour_to_click)
                center_x = int(M["m10"] / M["m00"])
                center_y = int(M["m01"] / M["m00"])
                offset_x, offset_y = frame_context.crop_offset
                click_pos = Point(center_x + offset_x, center_y + offset_y)
                log.debug(f"【追新模式】 点击目标坐标: {click_pos} (相对: ({center_x}, {center_y}), 偏移: {frame_context.crop_offset})")
                self.ctx.controller.click(click_pos)
                time.sleep(1)
                return self._click_confirm_after_strategy_chosen()

            log.debug("【追新模式】 当前屏幕无可选择目标，执行滑动...")
            self._swipe_strategy_list()
            self.screenshot()
            swipe_attempts += 1
        
        # 回退逻辑: 选择第一个
        frame_context = self.ctx.cv_service.run_pipeline('调查战略等级圈圈', self.last_screenshot)
        if frame_context.is_success and frame_context.contours:
            target_contour = frame_context.contours[0]
            M = cv2.moments(target_contour)
            center_x = int(M["m10"] / M["m00"])
            center_y = int(M["m01"] / M["m00"])
            offset_x, offset_y = frame_context.crop_offset
            click_pos = Point(center_x + offset_x, center_y + offset_y)
            log.debug(f"【追新模式-回退】 点击目标坐标: {click_pos} (相对: ({center_x}, {center_y}), 偏移: {frame_context.crop_offset})")
            self.ctx.controller.click(click_pos)
            time.sleep(1)
            return self._click_confirm_after_strategy_chosen()

        return self.round_fail("追新模式失败：未找到任何可选择的调查战略")

    def _swipe_strategy_list(self):
        """
        滑动调查战略列表
        """
        start = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
        end = start + Point(-800, 0)
        self.ctx.controller.drag_to(start=start, end=end)
        time.sleep(1)

    def _click_confirm_after_strategy_chosen(self) -> OperationRoundResult:
        """
        选择战略后，点击确定按钮
        """
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        ocr_word_list = list(ocr_result_map.keys())
        idx = str_utils.find_best_match_by_difflib(gt('确定', 'game'), ocr_word_list)
        if idx is None or idx < 0:
            return self.round_retry(status='未识别到确定按钮', wait=1)

        target_pos = ocr_result_map[ocr_word_list[idx]].max.center
        self.ctx.controller.click(target_pos)
        time.sleep(1)

        return self.round_wait(status='确定')

    def _choose_strategy_by_ocr(self) -> OperationRoundResult:
        """
        通过OCR识别选择调查战略
        """
        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        ocr_word_list = list(ocr_result_map.keys())
        target = gt(self.ctx.lost_void.challenge_config.investigation_strategy, 'game')
        idx = str_utils.find_best_match_by_difflib(target, ocr_word_list)

        if idx is None or idx < 0:
            is_after = str_utils.is_target_after_ocr_list(
                target_cn=self.ctx.lost_void.challenge_config.investigation_strategy,
                order_cn_list=[i.strategy_name for i in self.ctx.lost_void.investigation_strategy_list],
                ocr_result_list=ocr_word_list
            )

            start = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
            end = start + Point(800 * (-1 if is_after else 1), 0)
            self.ctx.controller.drag_to(start=start, end=end)
            return self.round_retry(status='未识别到目标调查战略', wait=1)

        target_pos = ocr_result_map[ocr_word_list[idx]].max.center
        self.ctx.controller.click(target_pos)
        time.sleep(1)

        return self._click_confirm_after_strategy_chosen()

    @node_from(from_name='选择调查战略')
    @operation_node(name='选择周期增益')
    def choose_buff(self) -> OperationRoundResult:
        mission_name = self.config.mission_name
        if mission_name == '特遣调查':
            return self.round_success(status='无需选择')
        else:
            return self.round_by_click_area(
                '迷失之地-战线肃清',
                f'周期增益-{self.ctx.lost_void.challenge_config.period_buff_no}',
                success_wait=1, retry_wait=1)

    @node_from(from_name='选择周期增益')
    @operation_node(name='下一步')
    def click_next(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='通用-出战', area_name='按钮-下一步',
                                                 until_find_all=[('通用-出战', '按钮-出战')],
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='下一步')
    @operation_node(name='检查预备编队')
    def check_predefined_team(self) -> OperationRoundResult:
        """
        根据配置判断是否需要切换编队
        :return:
        """
        self.use_priority_agent = False
        mission_name = self.config.mission_name
        if mission_name == '特遣调查':
            # 本周第一次挑战 且开启了优先级配队
            if (self.ctx.lost_void.challenge_config.choose_team_by_priority
                and self.run_record.complete_task_force_with_up == False):
                self.ctx.lost_void.predefined_team_idx = self.get_target_team_idx_by_priority()
                if self.ctx.lost_void.predefined_team_idx != -1:
                    self.use_priority_agent = True
                    return self.round_success(status='需选择预备编队')

        # 配置中选择特定编队
        if self.ctx.lost_void.challenge_config.predefined_team_idx != -1:
            self.ctx.lost_void.predefined_team_idx = self.ctx.lost_void.challenge_config.predefined_team_idx
            return self.round_success(status='需选择预备编队')

        return self.round_success(status='无需选择预备编队')

    def get_target_team_idx_by_priority(self) -> int:
        """
        根据当前识别的优先代理人 选择最合适的预备编队
        :return:
        """
        best_match_team_idx: int = self.ctx.lost_void.challenge_config.predefined_team_idx  # 如果都没匹配 使用默认的预备编队
        best_match_agent_cnt: int = 0
        for idx, team in enumerate(self.ctx.team_config.team_list):
            match_agent_cnt: int = 0
            for agent in self.priority_agent_list:
                if agent.agent_id in team.agent_id_list:
                    match_agent_cnt += 1

            if match_agent_cnt > best_match_agent_cnt:
                best_match_team_idx = idx
                best_match_agent_cnt = match_agent_cnt

        return best_match_team_idx

    @node_from(from_name='检查预备编队', status='需选择预备编队')
    @operation_node(name='选择预备编队')
    def choose_predefined_team(self) -> OperationRoundResult:
        op = ChoosePredefinedTeam(self.ctx, target_team_idx_list=[self.ctx.lost_void.predefined_team_idx])
        return self.round_by_op_result(op.execute())

    @node_from(from_name='检查预备编队', status='无需选择预备编队')
    @node_from(from_name='选择预备编队')
    @operation_node(name='出战')
    def deploy(self) -> OperationRoundResult:
        self.next_region_type = LostVoidRegionType.ENTRY
        op = Deploy(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='识别初始画面', status='迷失之地-大世界')
    @node_from(from_name='出战')
    @operation_node(name='加载自动战斗配置')
    def load_auto_op(self) -> OperationRoundResult:
        self.ctx.lost_void.init_auto_op()
        return self.round_success()

    @node_from(from_name='加载自动战斗配置')
    @node_from(from_name='层间移动')
    @operation_node(name='层间移动')
    def run_level(self) -> OperationRoundResult:
        log.info(f'推测楼层类型 {self.next_region_type.value.value}')
        op = LostVoidRunLevel(self.ctx, self.next_region_type)
        op_result = op.execute()
        if op_result.success:
            if op_result.status == LostVoidRunLevel.STATUS_NEXT_LEVEL:
                if op_result.data is not None:
                    self.next_region_type = LostVoidRegionType.from_value(op_result.data)
                else:
                    self.next_region_type = LostVoidRegionType.ENTRY

        return self.round_by_op_result(op_result)

    @node_from(from_name='层间移动', status=LostVoidRunLevel.STATUS_COMPLETE)
    @operation_node(name='通关后处理', node_max_retry_times=60)
    def after_complete(self) -> OperationRoundResult:
        screen_name = self.check_and_update_current_screen(self.last_screenshot)
        if screen_name != '迷失之地-入口':
            return self.round_retry('等待画面加载')

        self.run_record.add_complete_times()
        if self.use_priority_agent:
            self.run_record.complete_task_force_with_up = True

        if self.run_record.is_finished_by_day():
            return self.round_success(LostVoidApp.STATUS_ENOUGH_TIMES)

        return self.round_success(LostVoidApp.STATUS_AGAIN)

    @node_from(from_name='通关后处理')
    @operation_node(name='打开悬赏委托')
    def open_reward_list(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='迷失之地-入口', area_name='按钮-悬赏委托',
                                                 until_not_find_all=[('迷失之地-入口', '按钮-悬赏委托')],
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='打开悬赏委托')
    @operation_node(name='全部领取', node_max_retry_times=2)
    def claim_all(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='迷失之地-入口', area_name='按钮-悬赏委托-全部领取',
                                                 success_wait=1, retry_wait=0.5)

    @node_from(from_name='全部领取')
    @node_from(from_name='全部领取', success=False)
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        self.notify_screenshot = self.save_screenshot_bytes()  # 结束后通知的截图
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    op = LostVoidApp(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()
