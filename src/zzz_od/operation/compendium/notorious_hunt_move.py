import time

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from one_dragon.utils import str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon.yolo.detect_utils import DetectFrameResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class NotoriousHuntMove(ZOperation):
    """
    从 NotoriousHunt 提取的移动靠近机制。
    仅处理战斗前的移动：靠近目标 → 交互/选buff → 完成。

    调用方需要自行处理：加载自动战斗指令、等待画面加载、开始自动战斗。
    """

    def __init__(self, ctx: ZContext, buff_num: int = 3):
        """恶名狩猎战斗前移动操作

        Args:
            ctx: 上下文
            buff_num: 鸣徽选择编号 1~3，从左到右
        """
        ZOperation.__init__(
            self, ctx,
            op_name=gt('恶名狩猎战斗', 'game'),
        )
        self.buff_num: int = buff_num
        self.move_times: int = 0
        self.no_dis_times: int = 0

    @operation_node(name='初始化模型', is_start_node=True)
    def init_model(self) -> OperationRoundResult:
        """加载迷失之地检测模型 用于识别距离白点"""
        self.ctx.lost_void.init_lost_void_det_model()
        return self.round_success()

    @node_from(from_name='初始化模型')
    @operation_node(name='移动靠近交互', node_max_retry_times=10)
    def first_move(self) -> OperationRoundResult:
        result = self._move_by_hint()
        if result.is_success:
            self.no_dis_times = 0
        elif result.result == OperationRoundResultEnum.RETRY:
            self.no_dis_times += 1
        return result

    def _move_by_hint(self) -> OperationRoundResult:
        """根据画面显示的距离进行移动，出现交互按钮时停止。"""
        if self.move_times >= 10:
            return self.round_fail()

        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
        if result.is_success:
            self.ctx.controller.interact(press=True, press_time=0.2, release=True)
            return self.round_success(status=result.status, wait=2)

        det_result: DetectFrameResult = self.ctx.lost_void.detector.run(
            self.last_screenshot, label_list=['0001-距离']
        )
        self.ctx.auto_battle_context.check_battle_distance(self.last_screenshot)
        distance_pos = None
        if len(det_result.results) > 0:
            distance_pos = Point(
                det_result.results[0].center[0],
                det_result.results[0].center[1],
            )

        battle_result = self.round_by_find_area(
            self.last_screenshot, '恶名狩猎', '标识-BOSS血条'
        )
        if battle_result.is_success:
            return self.round_success(battle_result.status)

        if distance_pos is None:
            return self.round_retry(wait=1)

        current_distance = self.ctx.auto_battle_context.last_check_distance

        if self._turn_to_target(distance_pos):
            return self.round_wait(wait=0.5)
        else:
            log.info(f'识别距离: {current_distance}')
            press_time = current_distance / 7.2
            press_time = min(press_time, 5)
            if press_time > 0:
                self.ctx.controller.move_w(
                    press=True, press_time=press_time, release=True
                )
                self.move_times += 1
                return self.round_wait(wait=0.5)
            else:
                return self.round_retry(status='识别距离失败', wait=1)

    def _turn_to_target(self, target: Point) -> bool:
        """根据目标的位置进行转动。"""
        if target.x < 760:
            self.ctx.controller.turn_by_distance(-100)
        elif target.x < 860:
            self.ctx.controller.turn_by_distance(-50)
        elif target.x < 910:
            self.ctx.controller.turn_by_distance(-25)
        elif target.x > 1160:
            self.ctx.controller.turn_by_distance(+100)
        elif target.x > 1060:
            self.ctx.controller.turn_by_distance(+50)
        elif target.x > 1010:
            self.ctx.controller.turn_by_distance(+25)
        else:
            return False
        return True

    @node_from(from_name='移动靠近交互', status='按键-交互')
    @operation_node(name='交互')
    def move_and_interact(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
        if result.is_success:
            self.ctx.controller.interact(press=True, press_time=0.2, release=True)
            time.sleep(2)
            return self.round_retry()
        return self.round_success()

    @node_from(from_name='交互')
    @operation_node(name='选择')
    def choose_buff(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击')
        if result.is_success:
            return self.round_success()

        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
        if result.is_success:
            return self.round_success()

        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        choose_mr_list: list[MatchResult] = []

        for ocr_result, mrl in ocr_result_map.items():
            if str_utils.find_by_lcs(gt('选择', 'game'), ocr_result, percent=1):
                for mr in mrl:
                    choose_mr_list.append(mr)

        log.info('当前识别鸣徽选项数量 %d', len(choose_mr_list))

        if len(choose_mr_list) == 0:
            return self.round_retry('未识别到鸣徽选择', wait=1)

        choose_mr_list.sort(key=lambda x: x.left_top.x)

        to_choose_idx = self.buff_num - 1
        if to_choose_idx >= len(choose_mr_list):
            to_choose_idx = 0

        self.ctx.controller.click(choose_mr_list[to_choose_idx].center)
        return self.round_wait(wait=1)

    @node_from(from_name='选择')
    @operation_node(name='选择后移动', node_max_retry_times=18)
    def move_after_buff(self) -> OperationRoundResult:
        """选择buff后向白色提示点移动。"""
        direction_arr = [
            2, 3, 3, 2, 0, 1, 1, 0,
            2, 0, 3, 3, 1, 1, 2, 2, 0, 3,
        ]
        result = self._move_by_hint()
        if result.result == OperationRoundResultEnum.RETRY:
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
        return result

    @node_from(from_name='移动靠近交互', status='标识-BOSS血条')
    @node_from(from_name='选择', success=False)
    @node_from(from_name='选择后移动')
    @operation_node(name='移动完成')
    def move_done(self) -> OperationRoundResult:
        return self.round_success()
