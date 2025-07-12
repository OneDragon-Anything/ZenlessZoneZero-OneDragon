import time
from typing import Optional, ClassVar, List

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult, OperationRoundResultEnum
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon.yolo.detect_utils import DetectFrameResult
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.application.notorious_hunt.notorious_hunt_config import NotoriousHuntLevelEnum
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.challenge_mission.exit_in_battle import ExitInBattle
from zzz_od.operation.challenge_mission.restart_in_battle import RestartInBattle
from zzz_od.operation.choose_predefined_team import ChoosePredefinedTeam
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum


class NotoriousHunt(ZOperation):

    STATUS_NO_LEFT_TIMES: ClassVar[str] = '没有剩余次数'
    STATUS_WITH_LEFT_TIMES: ClassVar[str] = '有剩余次数'
    STATUS_CHARGE_NOT_ENOUGH: ClassVar[str] = '电量不足'
    STATUS_CHARGE_ENOUGH: ClassVar[str] = '电量充足'
    STATUS_FIGHT_TIMEOUT: ClassVar[str] = '战斗超时'

    def __init__(self, ctx: ZContext, plan: ChargePlanItem,
                 use_charge_power: bool = False,
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
                gt('恶名狩猎', 'game'),
                gt(plan.mission_type_name, 'game')
            )
        )

        self.plan: ChargePlanItem = plan
        self.use_charge_power: bool = use_charge_power  # 是否使用电量 深度追猎
        self.need_check_power: bool = need_check_power
        self.can_run_times: int = can_run_times

        self.auto_op: Optional[AutoBattleOperator] = None
        self.charge_left: Optional[int] = None
        self.charge_need: Optional[int] = None
        self.move_times: int = 0  # 移动次数
        self.no_dis_times: int = 0  # 识别不到距离的次数
        self.restart_times: int = 0  # 重新开始战斗次数

    @operation_node(name='等待入口加载', node_max_retry_times=60)
    def wait_entry_load(self) -> OperationRoundResult:
        screen = self.screenshot()
        r1 = self.round_by_find_area(screen, '恶名狩猎', '当期剩余奖励次数')
        if r1.is_success:
            return self.round_success(r1.status, wait=1)  # 画面加载有延时 稍微等待

        r2 = self.round_by_find_area(screen, '恶名狩猎', '按钮-街区')
        if r2.is_success:
            return self.round_success(r2.status, wait=1)  # 画面加载有延时 稍微等待

        return self.round_retry(r1.status, wait=1)

    @node_from(from_name='等待入口加载', status='按钮-街区')
    @operation_node(name='判断副本名称')
    def check_mission(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('恶名狩猎', '标题-副本名称')
        part = cv2_utils.crop_image_only(screen, area.rect)
        ocr_result_map = self.ctx.ocr.run_ocr(part)
        is_target_mission: bool = False  # 当前是否目标副本
        for ocr_result in ocr_result_map.keys():
            if str_utils.find_by_lcs(gt(self.plan.mission_type_name, 'game'), ocr_result, percent=0.5):
                is_target_mission = True
                break

        if is_target_mission:
            return self.round_success()
        else:
            return self.round_by_click_area('菜单', '返回', success_wait=1)

    @node_from(from_name='等待入口加载', status='当期剩余奖励次数')  # 最开始在外面的副本列表
    @node_from(from_name='判断副本名称', status='返回')  # 当前副本不符合 返回列表重新选择
    @operation_node(name='选择副本')
    def choose_mission(self) -> OperationRoundResult:
        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('恶名狩猎', '副本名称列表')
        part = cv2_utils.crop_image_only(screen, area.rect)

        ocr_result_map = self.ctx.ocr.run_ocr(part)
        for ocr_result, mrl in ocr_result_map.items():
            if str_utils.find_by_lcs(gt(self.plan.mission_type_name, 'game'), ocr_result, percent=0.5):
                to_click = mrl.max.center + area.left_top + Point(0, 100)
                if self.ctx.controller.click(to_click):
                    return self.round_success(wait=2)

        # 未匹配时 判断该往哪边滑动
        hunt_category = self.ctx.compendium_service.get_category_data('作战', '恶名狩猎')
        with_left: bool = False  # 当前识别有在目标左边的副本
        for mission_type in hunt_category.mission_type_list:
            if mission_type.mission_type_name == self.plan.mission_type_name:
                break

            find: bool = False  # 当前画面有没有识别到 mission_type
            for ocr_result, mrl in ocr_result_map.items():
                if str_utils.find_by_lcs(gt(mission_type.mission_type_name, 'game'), ocr_result, percent=0.5):
                    find = True
                    break

            if find:
                with_left = True

        drag_from = area.center
        if with_left:
            drag_to = Point(drag_from.x - 500, drag_from.y)
        else:
            drag_to = Point(drag_from.x + 500, drag_from.y)
        self.ctx.controller.drag_to(start=drag_from, end=drag_to)

        return self.round_retry(f'未能识别{self.plan.mission_type_name}', wait_round_time=2)

    @node_from(from_name='判断副本名称')  # 当前副本符合 继续选择
    @node_from(from_name='选择副本')
    @operation_node(name='选择深度追猎')
    def choose_by_use_power(self):
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '恶名狩猎', '按钮-深度追猎-ON')
        current_use_power = result.is_success  # 当前在深度追猎模式

        if self.use_charge_power == current_use_power:
            return self.round_success()

        # 选择深度追猎之后的对话框
        result = self.round_by_find_and_click_area(screen, '恶名狩猎', '按钮-深度追猎-确认')
        if result.is_success:
            return self.round_wait(result.status, wait=1)

        self.round_by_click_area('恶名狩猎', '按钮-深度追猎-ON')
        return self.round_retry(wait=1)

    @node_from(from_name='选择深度追猎')
    @operation_node(name='识别可运行次数')
    def check_can_run_times(self) -> OperationRoundResult:
        screen = self.screenshot()

        if self.use_charge_power:  # 深度追猎
            if self.need_check_power:
                area = self.ctx.screen_loader.get_area('恶名狩猎', '文本-剩余电量')
                part = cv2_utils.crop_image_only(screen, area.rect)
                ocr_result = self.ctx.ocr.run_ocr_single_line(part)
                self.charge_left = str_utils.get_positive_digits(ocr_result, None)
                if self.charge_left is None:
                    return self.round_retry(status='识别 %s 失败' % '剩余电量', wait=1)

                area = self.ctx.screen_loader.get_area('恶名狩猎', '文本-需要电量')
                part = cv2_utils.crop_image_only(screen, area.rect)
                ocr_result = self.ctx.ocr.run_ocr_single_line(part)
                self.charge_need = str_utils.get_positive_digits(ocr_result, None)
                if self.charge_need is None:
                    return self.round_retry(status='识别 %s 失败' % '需要电量', wait=1)

                log.info('所需电量 %d 剩余电量 %d', self.charge_need, self.charge_left)
                if self.charge_need > self.charge_left:
                    return self.round_success(NotoriousHunt.STATUS_CHARGE_NOT_ENOUGH)

                self.can_run_times = self.charge_left // self.charge_need
                max_need_run_times = self.plan.plan_times - self.plan.run_times

                if self.can_run_times > max_need_run_times:
                    self.can_run_times = max_need_run_times

                return self.round_success(NotoriousHunt.STATUS_CHARGE_ENOUGH)
            else:
                if self.can_run_times == 0:
                    return self.round_success(NotoriousHunt.STATUS_CHARGE_NOT_ENOUGH)
                else:
                    return self.round_success(NotoriousHunt.STATUS_CHARGE_ENOUGH)
        else:
            result = self.round_by_find_area(screen, '恶名狩猎', '按钮-无报酬模式')
            if result.is_success:  # 可能是其他设备挑战了 没有剩余次数了
                self.ctx.notorious_hunt_record.left_times = 0
                return self.round_success(NotoriousHunt.STATUS_NO_LEFT_TIMES)

            area = self.ctx.screen_loader.get_area('恶名狩猎', '剩余次数')
            part = cv2_utils.crop_image_only(screen, area.rect)

            ocr_result = self.ctx.ocr.run_ocr_single_line(part)
            left_times = str_utils.get_positive_digits(ocr_result, None)
            if left_times is None:  # 识别不到时 使用记录中的数量
                self.can_run_times = self.ctx.notorious_hunt_record.left_times
            else:
                self.can_run_times = left_times

            # 运行次数上限是计划剩余次数
            need_run_times = self.plan.plan_times - self.plan.run_times
            if self.can_run_times > need_run_times:
                self.can_run_times = need_run_times

            return self.round_success(NotoriousHunt.STATUS_WITH_LEFT_TIMES)

    @node_from(from_name='识别可运行次数', status=STATUS_CHARGE_ENOUGH)
    @node_from(from_name='识别可运行次数', status=STATUS_WITH_LEFT_TIMES)
    @operation_node(name='选择难度')
    def choose_level(self) -> OperationRoundResult:
        if self.plan.level == NotoriousHuntLevelEnum.DEFAULT.value.value:
            return self.round_success()

        self.round_by_click_area('恶名狩猎', '难度选择入口')
        time.sleep(1)

        screen = self.screenshot()
        area = self.ctx.screen_loader.get_area('恶名狩猎', '难度选择区域')
        result = self.round_by_ocr_and_click(screen, self.plan.level, area=area,
                                           success_wait=1)

        # 如果选择的是最高难度 那第一下有可能选中不到 多选一下兜底
        screen = self.screenshot()
        self.round_by_ocr_and_click(screen, self.plan.level, area=area,
                                    success_wait=1)

        if result.is_success:
            return result
        else:
            return self.round_retry(result.status, wait=1)

    @node_from(from_name='选择难度')
    @operation_node(name='下一步', node_max_retry_times=10)  # 部分机器加载较慢 延长出战的识别时间
    def click_next(self) -> OperationRoundResult:
        screen = self.screenshot()

        # 点击直到出战按钮出现
        result = self.round_by_find_area(screen, '实战模拟室', '出战')
        if result.is_success:
            return self.round_success(result.status)

        result = self.round_by_find_and_click_area(screen, '实战模拟室', '下一步')
        if result.is_success:
            time.sleep(0.5)
            self.ctx.controller.mouse_move(ScreenNormalWorldEnum.UID.value.center)  # 点击后 移开鼠标 防止识别不到出战
            return self.round_wait(result.status, wait=0.5)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='下一步')
    @operation_node(name='选择预备编队')
    def choose_predefined_team(self) -> OperationRoundResult:
        if self.plan.predefined_team_idx == -1:
            return self.round_success('无需选择预备编队')
        else:
            op = ChoosePredefinedTeam(self.ctx, [self.plan.predefined_team_idx])
            return self.round_by_op_result(op.execute())

    @node_from(from_name='选择预备编队')
    @operation_node(name='出战')
    def click_start(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(
            screen, '实战模拟室', '出战',
            success_wait=1, retry_wait_round=1
        )

    @node_from(from_name='出战')
    @node_from(from_name='重新开始-确认')
    @operation_node(name='加载自动战斗指令')
    def init_auto_battle(self) -> OperationRoundResult:
        if self.plan.predefined_team_idx == -1:
            auto_battle = self.plan.auto_battle_config
        else:
            team_list = self.ctx.team_config.team_list
            auto_battle = team_list[self.plan.predefined_team_idx].auto_battle

        self.ctx.lost_void.init_lost_void_det_model()  # 借用迷失之地的模型来识别距离白点

        return auto_battle_utils.load_auto_op(self, 'auto_battle', auto_battle)

    @node_from(from_name='加载自动战斗指令')
    @node_from(from_name='主动重新开始')
    @operation_node(name='等待战斗画面加载', node_max_retry_times=60, is_start_node=False)
    def wait_battle_screen(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '战斗画面', '按键-普通攻击')
        if result.is_success:
            return self.round_success(self.plan.mission_type_name)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='移动靠近交互', node_max_retry_times=10)
    def first_move(self) -> OperationRoundResult:
        result = self._move_by_hint()
        if result.is_success:
            self.no_dis_times = 0
        elif result.result == OperationRoundResultEnum.RETRY:
            self.no_dis_times += 1
        return result

    def _move_by_hint(self) -> OperationRoundResult:
        """
        根据画面显示的距离进行移动
        出现交互的按钮时候就可以停止了
        """
        if self.move_times >= 10:
            return self.round_fail()

        screen = self.screenshot()

        result = self.round_by_find_area(screen, '战斗画面', '按键-交互')
        if result.is_success:
            return self.round_success()

        det_result: DetectFrameResult = self.ctx.lost_void.detector.run(screen, label_list=['0001-距离'])
        self.auto_op.auto_battle_context.check_battle_distance(screen)
        distance_pos = None
        if len(det_result.results) > 0:
            distance_pos = Point(det_result.results[0].center[0], det_result.results[0].center[1])

        battle_result = self.round_by_find_area(screen, '恶名狩猎', '标识-BOSS血条')
        if battle_result.is_success:
            return self.round_success(battle_result.status)

        if distance_pos is None:
            return self.round_retry(wait=1)

        current_distance = self.auto_op.auto_battle_context.last_check_distance

        turn_result = self.turn_to_target(distance_pos)
        if turn_result:
            return self.round_wait(wait=0.5)
        else:
            self.last_distance = current_distance
            press_time = self.auto_op.auto_battle_context.last_check_distance / 7.2  # 朱鸢测出来的速度
            self.ctx.controller.move_w(press=True, press_time=press_time, release=True)
            self.move_times += 1
            return self.round_wait(wait=0.5)

    def turn_to_target(self, target: Point) -> bool:
        """
        根据目标的位置 进行转动
        @param target: 目标位置
        @return: 是否进行了转动
        """
        if target.x < 760:
            self.ctx.controller.turn_by_distance(-100)
            return True
        elif target.x < 860:
            self.ctx.controller.turn_by_distance(-50)
            return True
        elif target.x < 910:
            self.ctx.controller.turn_by_distance(-25)
            return True
        elif target.x > 1160:
            self.ctx.controller.turn_by_distance(+100)
            return True
        elif target.x > 1060:
            self.ctx.controller.turn_by_distance(+50)
            return True
        elif target.x > 1010:
            self.ctx.controller.turn_by_distance(+25)
            return True
        else:
            return False

    @node_from(from_name='移动靠近交互')
    @operation_node(name='交互')
    def move_and_interact(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '战斗画面', '按键-交互')
        if result.is_success:
            self.ctx.controller.interact(press=True, press_time=0.2, release=True)
            time.sleep(2)
            return self.round_retry()
        else:
            return self.round_success()

    @node_from(from_name='交互')
    @operation_node(name='选择')
    def choose_buff(self) -> OperationRoundResult:
        screen = self.screenshot()

        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        choose_mr_list: List[MatchResult] = []

        for ocr_result, mrl in ocr_result_map.items():
            if str_utils.find_by_lcs(gt('选择', 'game'), ocr_result, percent=0.5):
                for mr in mrl:
                    choose_mr_list.append(mr)

        log.info('当前识别鸣徽选项数量 %d', len(choose_mr_list))

        if len(choose_mr_list) == 0:
            return self.round_retry('未识别到鸣徽选择', wait=1)

        # 按横坐标从左往右排序
        choose_mr_list.sort(key=lambda x: x.left_top.x)

        to_choose_idx = self.plan.notorious_hunt_buff_num - 1
        if to_choose_idx >= len(choose_mr_list):
            to_choose_idx = 0

        to_click = choose_mr_list[to_choose_idx].center
        self.ctx.controller.click(to_click)

        return self.round_success(wait=3)  # 多等待一会 等白色距离点出现

    @node_from(from_name='选择')
    @operation_node(name='选择后移动', node_max_retry_times=18)
    def move_after_buff(self) -> OperationRoundResult:
        """
        选择buff后 向白色提示点移动
        :return:
        """
        direction_arr = [
            2, 3, 3, 2, 0, 1, 1, 0,  # 左右右左 前后后前 往四个方向都走一段试试
            2, 0, 3, 3, 1, 1, 2, 2, 0, 3,  # 左上 右右 下下 左左 上右 在附近转一圈
        ]
        result = self._move_by_hint()
        if result.result == OperationRoundResultEnum.RETRY:
            # 识别不到白点 可能是有因为没吃到红心 在周围随机移动
            direction = direction_arr[self.no_dis_times % len(direction_arr)]
            if direction == 0:
                self.ctx.controller.move_w(press=True, press_time=0.5, release=True)
            elif direction == 1:
                self.ctx.controller.move_s(press=True, press_time=0.5, release=True)
            elif direction == 2:
                self.ctx.controller.move_a(press=True, press_time=0.5, release=True)
            elif direction == 3:
                self.ctx.controller.move_d(press=True, press_time=0.5, release=True)
            self.no_dis_times += 1
        else:
            self.no_dis_times = 0

        if result.is_success:
            self.auto_op.start_running_async()
        return result

    @node_from(from_name='选择后移动')
    @node_from(from_name='战斗失败', status='战斗结果-倒带')
    @operation_node(name='自动战斗', mute=True, timeout_seconds=600)
    def auto_battle(self) -> OperationRoundResult:
        if self.auto_op.auto_battle_context.last_check_end_result is not None:
            auto_battle_utils.stop_running(self.auto_op)
            return self.round_success(status=self.auto_op.auto_battle_context.last_check_end_result)
        now = time.time()
        screen = self.screenshot()

        self.auto_op.auto_battle_context.check_battle_state(screen, now, check_battle_end_normal_result=True)

        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='自动战斗', status='普通战斗-撤退')
    @operation_node(name='战斗失败')
    def battle_fail(self) -> OperationRoundResult:
        screen = self.screenshot()
        result = self.round_by_find_and_click_area(screen, '战斗画面', '战斗结果-倒带')

        if result.is_success:
            self.auto_op.auto_battle_context.last_check_end_result = None
            self.auto_op.start_running_async()
            return self.round_success(result.status, wait=1)

        result = self.round_by_find_and_click_area(screen, '战斗画面', '战斗结果-撤退')
        if result.is_success:
            return self.round_success(result.status, wait=1)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='战斗失败', status='战斗结果-撤退')
    @operation_node(name='战斗失败退出')
    def battle_fail_exit(self) -> OperationRoundResult:
        screen = self.screenshot()
        result = self.round_by_find_and_click_area(screen, '战斗画面', '战斗结果-退出')

        if result.is_success:  # 战斗失败 返回失败到外层 中断后续挑战
            return self.round_fail(result.status, wait=10)
        else:
            return self.round_retry(result.status, wait=1)

    @node_from(from_name='自动战斗')
    @operation_node(name='战斗结束')
    def after_battle(self) -> OperationRoundResult:
        self.can_run_times -= 1
        if self.use_charge_power:
            self.ctx.charge_plan_config.add_plan_run_times(self.plan)
        else:
            self.ctx.notorious_hunt_record.left_times = self.ctx.notorious_hunt_record.left_times - 1
            self.ctx.notorious_hunt_config.add_plan_run_times(self.plan)
        return self.round_success()

    @node_from(from_name='战斗结束')
    @operation_node(name='判断下一次')
    def check_next(self) -> OperationRoundResult:
        screen = self.screenshot()
        if self.can_run_times == 0:
            return self.round_by_find_and_click_area(screen, '战斗画面', '战斗结果-完成',
                                                     success_wait=5, retry_wait_round=1)
        else:
            return self.round_by_find_and_click_area(screen, '战斗画面', '战斗结果-再来一次',
                                                     success_wait=1, retry_wait_round=1)

    @node_from(from_name='判断下一次', success=False)
    @operation_node(name='判断下一次失败处理')
    def no_left_times(self) -> OperationRoundResult:
        # 本地记录的剩余次数错误 找不到再来一次
        # 可能在其它设备上完成了挑战 也可能是上面识别错了
        if self.use_charge_power:
            pass
        else:
            self.ctx.notorious_hunt_record.left_times = 0
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '战斗画面', '战斗结果-完成',
                                                 success_wait=5, retry_wait_round=1)

    @node_from(from_name='判断下一次', status='战斗结果-再来一次')
    @operation_node(name='重新开始-确认')
    def restart_confirm(self) -> OperationRoundResult:
        if self.use_charge_power:  # 使用体力的时候不需要重新确认
            return self.round_success()
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '恶名狩猎', '重新开始-确认',
                                                 success_wait=1, retry_wait_round=1)

    @node_from(from_name='判断下一次', status='战斗结果-完成')
    @node_from(from_name='判断下一次失败处理', status='战斗结果-完成')
    @operation_node(name='等待返回入口', node_max_retry_times=60)
    def wait_back_to_entry(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '恶名狩猎', '剩余奖励次数')
        if result.is_success:  # 普通模式
            return self.round_success(wait=1)

        result = self.round_by_find_area(screen, '恶名狩猎', '按钮-街区')
        if result.is_success:  # 深度追猎
            return self.round_success(wait=1)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='移动靠近交互', success=False)
    @node_from(from_name='自动战斗', success=False, status=Operation.STATUS_TIMEOUT)
    @operation_node(name='退出战斗')
    def exit_battle(self) -> OperationRoundResult:
        auto_battle_utils.stop_running(self.auto_op)
        op = ExitInBattle(self.ctx, '战斗-挑战结果-失败', '按钮-退出')
        return self.round_by_op_result(op.execute())

    @node_from(from_name='退出战斗')
    @operation_node(name='点击挑战结果退出')
    def click_result_exit(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(screen_name='战斗-挑战结果-失败', area_name='按钮-退出',
                                                   until_not_find_all=[('战斗-挑战结果-失败', '按钮-退出')],
                                                   success_wait=1, retry_wait=1)
        if result.is_success:
            return self.round_fail(status=NotoriousHunt.STATUS_FIGHT_TIMEOUT)

    @node_from(from_name='选择后移动', success=False)
    @operation_node(name='主动重新开始')
    def restart_battle(self) -> OperationRoundResult:
        """
        吃不到红心的情况 重新开始
        :return:
        """
        if self.restart_times == 0:
            op = RestartInBattle(self.ctx)
            op_result = op.execute()
            self.restart_times += 1
            return self.round_by_op_result(op_result)
        else:
            op = ExitInBattle(self.ctx)
            op_result = op.execute()
            if op_result.success:
                return self.round_fail(status='无法开启战斗')
            else:
                return self.round_retry(op_result.status, wait=1)

    def handle_pause(self, e=None):
        if self.auto_op is not None:
            self.auto_op.stop_running()

    def handle_resume(self, e=None):
        auto_battle_utils.resume_running(self.auto_op)

    def after_operation_done(self, result: OperationResult):
        ZOperation.after_operation_done(self, result)
        if self.auto_op is not None:
            self.auto_op.dispose()
            self.auto_op = None

def __debug_charge():
    """
    测试电量识别
    @return:
    """
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('_1742622386361')
    area = ctx.screen_loader.get_area('恶名狩猎', '文本-剩余电量')
    part = cv2_utils.crop_image_only(screen, area.rect)
    ocr_result = ctx.ocr.run_ocr_single_line(part)
    print(ocr_result)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.start_running()
    op = NotoriousHunt(
        ctx,
        ChargePlanItem(
            category_name='恶名狩猎',
            mission_type_name='冥宁芙·双子',
            level=NotoriousHuntLevelEnum.DEFAULT.value.value,
            auto_battle_config='专属配队-简',
            predefined_team_idx=0,
        ),
        use_charge_power=True)
    op.can_run_times = 1
    op.auto_op = None
    op.init_auto_battle()

    op.execute()


if __name__ == '__main__':
    __debug()
