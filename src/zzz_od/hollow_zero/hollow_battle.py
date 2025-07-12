import time

from cv2.typing import MatLike
from typing import Optional, ClassVar

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext
from zzz_od.hollow_zero.game_data.hollow_zero_event import HollowZeroSpecialEvent
from zzz_od.operation.zzz_operation import ZOperation


class HollowBattle(ZOperation):

    STATUS_NEED_SPECIAL_MOVE: ClassVar[str] = '需要移动'
    STATUS_NO_NEED_SPECIAL_MOVE: ClassVar[str] = '不需要移动'
    STATUS_FAIL_TO_MOVE: ClassVar[str] = '移动失败'

    def __init__(self, ctx: ZContext, is_critical_stage: bool = False):
        """
        确定进入战斗后调用
        战斗后的按钮点击退出交由外层实现
        :param ctx:
        """
        event_name = HollowZeroSpecialEvent.IN_BATTLE.value.event_name
        ZOperation.__init__(
            self, ctx,
            op_name=gt(event_name, 'game')
        )

        self.is_critical_stage: bool = is_critical_stage  # 是否关键进展
        self.auto_op: Optional[AutoBattleOperator] = None
        self.move_times: int = 0  # 向前移动的次数
        self.turn_times: int = 0  # 转动的次数
        self.last_distance: Optional[float] = None  # 上次移动前的距离
        self.last_stuck_distance: Optional[float] = None  # 上次受困显示的距离
        self.stuck_move_direction: int = 0  # 受困时移动的方向
        self.last_distance_to_turn: Optional[float] = None  # 上次转向的距离

    def handle_init(self):
        self.distance_pos: Optional[Rect] = None  # 显示距离的区域

    @operation_node(name='加载自动战斗指令', is_start_node=True)
    def load_auto_op(self) -> OperationRoundResult:
        return auto_battle_utils.load_auto_op(
            self, 'auto_battle',
            self.ctx.hollow_zero_challenge_config.auto_battle
        )

    @node_from(from_name='加载自动战斗指令')
    @operation_node(name='等待战斗画面加载', node_max_retry_times=60)
    def wait_battle_screen(self) -> OperationRoundResult:
        screen = self.screenshot()
        result = self.round_by_find_area(screen, '战斗画面', '按键-普通攻击', retry_wait_round=1)
        return result

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='识别特殊移动')
    def check_special_move(self):
        screen = self.screenshot()
        self.check_distance_to_move(screen)

        if self.auto_op.auto_battle_context.with_distance_times >= 10:
            return self.round_success(HollowBattle.STATUS_NEED_SPECIAL_MOVE)
        if self.auto_op.auto_battle_context.without_distance_times >= 10:
            self.auto_op.start_running_async()
            return self.round_success(HollowBattle.STATUS_NO_NEED_SPECIAL_MOVE)

        return self.round_wait()

    @node_from(from_name='识别特殊移动', status=STATUS_NEED_SPECIAL_MOVE)
    @operation_node(name='副本特殊移动')
    def special_move(self):
        if (self.ctx.hollow.level_info.is_mission_type('旧都列车', 2)
            and self.ctx.hollow.level_info.level == 2):
            self.ctx.controller.move_w(press=True, press_time=1.5)
        else:
            self.ctx.controller.move_w(press=True, press_time=1.5)

        return self.round_success()

    @node_from(from_name='副本特殊移动')
    @node_from(from_name='自动战斗', status=STATUS_NEED_SPECIAL_MOVE)
    @operation_node(name='向前移动准备战斗')
    def move_to_battle(self) -> OperationRoundResult:
        screen = self.screenshot()
        self.check_distance_to_move(screen)

        if self.distance_pos is None:
            if self.auto_op.auto_battle_context.without_distance_times >= 10:
                self.auto_op.start_running_async()
                return self.round_success()
            else:
                return self.round_wait(wait=0.02)

        if self.move_times >= 20 or self.turn_times >= 60:
            # 移动比较久也没到 就自动退出了
            return self.round_fail(HollowBattle.STATUS_FAIL_TO_MOVE)

        current_distance = self.auto_op.auto_battle_context.last_check_distance
        if self.last_distance is not None and abs(self.last_distance - current_distance) < 0.5:
            log.info('上次移动后距离没有发生变化 尝试脱困')
            if self.last_stuck_distance is not None and abs(self.last_stuck_distance - current_distance) < 0.5:
                # 困的时候显示的距离跟上次困住的一样 代表脱困方向不对 换一个
                log.info('上次脱困后距离没有发生变化 更换脱困方向')
                self.stuck_move_direction += 1
                if self.stuck_move_direction >= 6:
                    self.stuck_move_direction = 0

            self.last_distance = current_distance
            self.last_stuck_distance = current_distance

            self._get_rid_of_stuck()

            return self.round_wait(wait=0.5)

        pos = self.distance_pos.center
        if pos.x < 900:
            self.ctx.controller.turn_by_distance(-50)
            self.turn_times += 1
            return self.round_wait(wait=0.5)
        elif pos.x > 1100:
            self.ctx.controller.turn_by_distance(+50)
            self.turn_times += 1
            return self.round_wait(wait=0.5)
        else:
            self.last_distance = current_distance
            press_time = self.auto_op.auto_battle_context.last_check_distance / 7.2  # 朱鸢测出来的速度
            self.ctx.controller.move_w(press=True, press_time=press_time, release=True)
            self.move_times += 1
            self.last_distance_to_turn = None  # 移动完后重新识别
            return self.round_wait(wait=0.5)

    def _get_rid_of_stuck(self):
        log.info('本次脱困方向 %s' % self.stuck_move_direction)
        if self.stuck_move_direction == 0:  # 向左走
            self.ctx.controller.move_a(press=True, press_time=1, release=True)
        elif self.stuck_move_direction == 1:  # 向右走
            self.ctx.controller.move_d(press=True, press_time=1, release=True)
        elif self.stuck_move_direction == 2:  # 后左前 1秒
            self.ctx.controller.move_s(press=True, press_time=1, release=True)
            self.ctx.controller.move_a(press=True, press_time=1, release=True)
            self.ctx.controller.move_w(press=True, press_time=1, release=True)
        elif self.stuck_move_direction == 3:  # 后右前 1秒
            self.ctx.controller.move_s(press=True, press_time=1, release=True)
            self.ctx.controller.move_d(press=True, press_time=1, release=True)
            self.ctx.controller.move_w(press=True, press_time=1, release=True)
        elif self.stuck_move_direction == 4:  # 后左前 2秒
            self.ctx.controller.move_s(press=True, press_time=2, release=True)
            self.ctx.controller.move_a(press=True, press_time=2, release=True)
            self.ctx.controller.move_w(press=True, press_time=2, release=True)
        elif self.stuck_move_direction == 5:  # 后右前 2秒
            self.ctx.controller.move_s(press=True, press_time=2, release=True)
            self.ctx.controller.move_d(press=True, press_time=2, release=True)
            self.ctx.controller.move_w(press=True, press_time=2, release=True)

    @node_from(from_name='识别特殊移动', status=STATUS_NO_NEED_SPECIAL_MOVE)
    @node_from(from_name='向前移动准备战斗')
    @operation_node(name='自动战斗', timeout_seconds=600, mute=True)
    def auto_battle(self) -> OperationRoundResult:
        self.move_times = 0
        self.turn_times = 0
        if self.auto_op.auto_battle_context.last_check_end_result is not None:
            auto_battle_utils.stop_running(self.auto_op)
            return self.round_success(status=self.auto_op.auto_battle_context.last_check_end_result)

        if self.auto_op.auto_battle_context.with_distance_times >= 5:
            auto_battle_utils.stop_running(self.auto_op)
            return self.round_success(status=HollowBattle.STATUS_NEED_SPECIAL_MOVE)

        now = time.time()
        screen = self.screenshot()

        self.auto_op.auto_battle_context.check_battle_state(screen, now,
                                           check_battle_end_normal_result=True,
                                           check_battle_end_hollow_result=True,
                                           check_distance=True)

        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)


    @node_from(from_name='自动战斗', status='零号空洞-结算周期上限')
    @operation_node(name='结算周期上限')
    def period_reward_full(self) -> OperationRoundResult:
        time.sleep(1)  # 第一次稍等等一段时间 避免按键还不能响应
        screen = self.screenshot()
        self.ctx.hollow_zero_record.period_reward_complete = True
        return self.round_by_find_and_click_area(screen, '零号空洞-战斗', '结算周期上限-确认',
                                           success_wait=1, retry_wait=1)

    @node_from(from_name='结算周期上限')
    @node_from(from_name='自动战斗', status='零号空洞-挑战结果')
    @operation_node(name='战斗结果-确定')
    def after_battle(self) -> OperationRoundResult:
        # 找到后稍微等待: 1.按钮刚出来的时候按不会有响应 2. 奖励列表可能还没有出现
        time.sleep(2)
        screen = self.screenshot()

        # 有时候可能会识别到背景上的挑战结果 这时候也尝试点
        result = self.round_by_find_and_click_area(screen, '零号空洞-战斗', '结算周期上限-确认')
        if result.is_success:
            return self.round_wait()  # 每次开始都有等待 这里就不等了

        area = self.ctx.screen_loader.get_area('零号空洞-战斗', '战斗结果-确定')
        result = self.round_by_ocr_and_click(screen, '确定', area=area)
        if result.is_success:
            return self.round_success(result.status, wait=1)

        # 匹配不到的时候 随便点击 防止有一些新的对话框出现没有处理到
        self.round_by_click_area('零号空洞-战斗', '战斗结果-确定')
        return self.round_retry(result.status, wait=1)

    @node_from(from_name='自动战斗', status='普通战斗-完成')
    @operation_node(name='普通战斗-完成')
    def mission_complete(self) -> OperationRoundResult:
        # 在battle_context里会判断这个的出现
        # 找到后稍微等待: 1.按钮刚出来的时候按不会有响应 2. 奖励列表可能还没有出现
        time.sleep(2)
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '零号空洞-战斗', '通关-丁尼奖励')
        if not result.is_success:
            # 领满奖励了
            self.ctx.hollow_zero_record.period_reward_complete = True
            self.save_screenshot()
        else:
            # 防止因为动画效果 奖励还没有出现 就出现了按钮
            self.ctx.hollow_zero_record.period_reward_complete = False

        return self.round_success(status='普通战斗-完成')

    @node_from(from_name='战斗结果-确定')
    @operation_node(name='更新楼层信息')
    def update_level_info(self) -> OperationRoundResult:
        self.ctx.hollow.update_to_next_level()
        return self.round_success()

    @node_from(from_name='自动战斗', status='普通战斗-撤退')
    @operation_node(name='战斗撤退')
    def battle_fail(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '战斗画面', '战斗结果-撤退',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='自动战斗', success=False, status=Operation.STATUS_TIMEOUT)
    @node_from(from_name='向前移动准备战斗', success=False, status=STATUS_FAIL_TO_MOVE)
    @operation_node(name='移动失败')
    def move_fail(self) -> OperationRoundResult:
        if self.auto_op is not None:
            self.auto_op.stop_running()
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '零号空洞-战斗', '退出战斗')
        if result.is_success:
            return self.round_success(wait=0.5)  # 稍微等一下让按钮可按

        return self.round_by_click_area('战斗画面', '菜单',
                                        success_wait=1, retry_wait=1)

    @node_from(from_name='移动失败')
    @operation_node(name='点击退出')
    def click_exit(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '零号空洞-战斗', '退出战斗',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击退出')
    @operation_node(name='点击退出确认')
    def click_exit_confirm(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '零号空洞-战斗', '退出战斗-确认',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击退出确认')
    @operation_node(name='等待退出', node_max_retry_times=20)
    def wait_exit(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_area(screen, '零号空洞-事件', '通关-完成',
                                       success_wait=2, retry_wait=1)  # 找到后稍微等待 按钮刚出来的时候按没有用

    def check_distance_to_move(self, screen: MatLike) -> None:
        mr = self.auto_op.auto_battle_context.check_battle_distance(screen, self.last_distance_to_turn)

        if mr is None:
            self.distance_pos = None
        else:
            self.distance_pos = mr.rect
            self.last_distance_to_turn = mr.data

    def _on_pause(self, e=None):
        ZOperation._on_pause(self, e)
        auto_battle_utils.stop_running(self.auto_op)

    def _on_resume(self, e=None):
        ZOperation._on_resume(self, e)
        auto_battle_utils.resume_running(self.auto_op)

    def after_operation_done(self, result: OperationResult):
        ZOperation.after_operation_done(self, result)
        if self.auto_op is not None:
            self.auto_op.dispose()
            self.auto_op = None


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.start_running()
    ctx.init_ocr()
    op = HollowBattle(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()

