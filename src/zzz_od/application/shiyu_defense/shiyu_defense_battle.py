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
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class ShiyuDefenseBattle(ZOperation):

    STATUS_NEED_SPECIAL_MOVE: ClassVar[str] = '需要移动'
    STATUS_NO_NEED_SPECIAL_MOVE: ClassVar[str] = '不需要移动'
    STATUS_FAIL_TO_MOVE: ClassVar[str] = '移动失败'
    STATUS_BATTLE_TIMEOUT: ClassVar[str] = '战斗超时'
    STATUS_TO_NEXT_PHASE: ClassVar[str] = '下一阶段'

    def __init__(self, ctx: ZContext, predefined_team_idx: int):
        """
        确定进入战斗后调用
        无论胜利失败 最后画面会在
        - 战斗胜利 - 下一层的战斗开始画面
        - 战斗胜利 - 结算画面
        - 失败 - 选择节点画面 左上角有街区2字
        @param ctx: 上下文
        @param predefined_team_idx: 预备编队的下标
        """
        ZOperation.__init__(
            self, ctx,
            op_name='%s %s' % (gt('式舆防卫战', 'game'), gt('自动战斗'))
        )

        self.team_config: PredefinedTeamInfo = self.ctx.team_config.get_team_by_idx(predefined_team_idx)
        self.auto_op: Optional[AutoBattleOperator] = None
        self.distance_pos: Optional[Rect] = None  # 显示距离的区域
        self.move_times: int = 0  # 移动次数
        self.battle_fail: Optional[str] = None  # 战斗失败的原因
        self.find_interact_btn_times: int = 0  # 发现交互按钮的次数

    @operation_node(name='加载自动战斗指令', is_start_node=True)
    def load_auto_op(self) -> OperationRoundResult:
        return auto_battle_utils.load_auto_op(
            self, 'auto_battle',
            self.ctx.battle_assistant_config.auto_battle if self.team_config is None else self.team_config.auto_battle
        )

    @node_from(from_name='加载自动战斗指令')
    @operation_node(name='等待战斗画面加载', node_max_retry_times=60)
    def wait_battle_screen(self) -> OperationRoundResult:
        screen = self.screenshot()
        result = self.round_by_find_area(screen, '战斗画面', '按键-普通攻击', retry_wait_round=1)
        return result

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='向前移动准备战斗')
    def start_move(self):
        screen = self.screenshot()
        self.check_distance(screen)

        if self.distance_pos is None:
            if self.auto_op.auto_battle_context.without_distance_times >= 10:
                self.auto_op.start_running_async()
                self.move_times = 0
                return self.round_success()
            else:
                return self.round_wait(wait=0.02)

        if self.move_times >= 20:
            # 移动比较久也没到 就自动退出了
            self.battle_fail = ShiyuDefenseBattle.STATUS_FAIL_TO_MOVE
            return self.round_fail(ShiyuDefenseBattle.STATUS_FAIL_TO_MOVE)

        pos = self.distance_pos.center
        if pos.x < 900:
            self.ctx.controller.turn_by_distance(-50)
            return self.round_wait(wait=0.5)
        elif pos.x > 1100:
            self.ctx.controller.turn_by_distance(+50)
            return self.round_wait(wait=0.5)
        else:
            press_time = self.auto_op.auto_battle_context.last_check_distance / 7.2  # 朱鸢测出来的速度
            self.ctx.controller.move_w(press=True, press_time=press_time, release=True)
            self.move_times += 1
            return self.round_wait(wait=0.5)

    @node_from(from_name='向前移动准备战斗')
    @operation_node(name='自动战斗', timeout_seconds=600, mute=True)
    def auto_battle(self) -> OperationRoundResult:
        if self.auto_op.auto_battle_context.last_check_end_result is not None:
            auto_battle_utils.stop_running(self.auto_op)
            return self.round_success(status=self.auto_op.auto_battle_context.last_check_end_result)

        if self.auto_op.auto_battle_context.with_distance_times >= 5:
            auto_battle_utils.stop_running(self.auto_op)
            return self.round_success(status=ShiyuDefenseBattle.STATUS_NEED_SPECIAL_MOVE)

        now = time.time()
        screen = self.screenshot()

        in_battle = self.auto_op.auto_battle_context.check_battle_state(
            screen, now,
            check_battle_end_normal_result=True,
            check_battle_end_defense_result=True,
            check_distance=True)

        if not in_battle:
            result = self.round_by_find_area(screen, '战斗画面', '按键-交互')
            if result.is_success:
                self.find_interact_btn_times += 1
            else:
                self.find_interact_btn_times = 0

            if self.find_interact_btn_times >= 10:
                auto_battle_utils.stop_running(self.auto_op)
                return self.round_success(status=ShiyuDefenseBattle.STATUS_NEED_SPECIAL_MOVE)

        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='自动战斗', status=STATUS_NEED_SPECIAL_MOVE)
    @operation_node(name='战斗后移动', node_max_retry_times=5)
    def move_after_battle(self) -> OperationRoundResult:
        screen = self.screenshot()

        result1 = self.round_by_find_area(screen, '战斗画面', '按键-交互')
        if result1.is_success:
            self.ctx.controller.interact(press=True, press_time=0.2, release=True)
            return self.round_wait(result1.status, wait=0.5)

        result2 = self.round_by_find_area(screen, '战斗画面', '按键-普通攻击')
        if not result2.is_success:
            # 交互和普通攻击都没有找到 说明战斗胜利了
            return self.round_success(ShiyuDefenseBattle.STATUS_TO_NEXT_PHASE)

        auto_battle_utils.check_astra_and_switch(self.auto_op)  # 移动前如果是耀嘉音就切人

        self.check_distance(screen)

        if self.distance_pos is None:
            # 丢失距离后 当前无法识别下层入口 只能失败退出
            return self.round_retry(wait=1)

        if self.move_times >= 60:
            # 移动比较久也没到 就自动退出了
            self.battle_fail = ShiyuDefenseBattle.STATUS_FAIL_TO_MOVE
            return self.round_fail(ShiyuDefenseBattle.STATUS_FAIL_TO_MOVE)

        pos = self.distance_pos.center
        if pos.x < 900:
            self.ctx.controller.turn_by_distance(-50)
            return self.round_wait(wait=0.5)
        elif pos.x > 1100:
            self.ctx.controller.turn_by_distance(+50)
            return self.round_wait(wait=0.5)
        else:
            press_time = self.auto_op.auto_battle_context.last_check_distance / 7.2  # 朱鸢测出来的速度
            if press_time > 1:  # 不要移动太久 防止错过了下层入口
                press_time = 1
            self.ctx.controller.move_w(press=True, press_time=press_time, release=True)
            self.move_times += 1
            return self.round_wait(wait=0.5)

    def check_distance(self, screen: MatLike) -> None:
        mr = self.auto_op.auto_battle_context.check_battle_distance(screen)

        if mr is None:
            self.distance_pos = None
        else:
            self.distance_pos = mr.rect

    @node_from(from_name='自动战斗', success=False, status=Operation.STATUS_TIMEOUT)
    @operation_node(name='战斗超时')
    def battle_timeout(self) -> OperationRoundResult:
        self.battle_fail = ShiyuDefenseBattle.STATUS_BATTLE_TIMEOUT
        return self.round_success()

    @node_from(from_name='向前移动准备战斗', success=False, status=STATUS_FAIL_TO_MOVE)
    @node_from(from_name='战斗超时')
    @node_from(from_name='战斗后移动', success=False)
    @operation_node(name='主动退出')
    def voluntary_exit(self) -> OperationRoundResult:
        auto_battle_utils.stop_running(self.auto_op)
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '式舆防卫战', '退出战斗')
        if result.is_success:
            return self.round_success(wait=0.5)  # 稍微等一下让按钮可按

        return self.round_by_click_area('战斗画面', '菜单',
                                        success_wait=1, retry_wait=1)

    @node_from(from_name='主动退出')
    @operation_node(name='点击退出')
    def click_exit(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '式舆防卫战', '退出战斗',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击退出')
    @operation_node(name='点击退出确认')
    def click_exit_confirm(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '零号空洞-战斗', '退出战斗-确认',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='自动战斗', status='战斗结束-撤退')
    @operation_node(name='战斗失败撤退')
    def battle_fail_exit(self) -> OperationRoundResult:
        screen = self.screenshot()
        self.battle_fail = '战斗结束-撤退'
        return self.round_by_find_and_click_area(screen, '式舆防卫战', '战斗结束-撤退',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击退出确认')
    @node_from(from_name='战斗失败撤退')
    @operation_node(name='等待退出', node_max_retry_times=60)
    def wait_exit(self) -> OperationRoundResult:
        screen = self.screenshot()
        result = self.round_by_find_area(screen, '式舆防卫战', '街区')

        if result.is_success:
            if self.battle_fail is None:
                return self.round_success(result.status)
            else:
                return self.round_fail(self.battle_fail)

        return self.round_retry(result.status, wait=1)

    def _on_pause(self, e=None):
        ZOperation._on_pause(self, e)
        auto_battle_utils.stop_running(self.auto_op)

    def _on_resume(self, e=None):
        ZOperation._on_resume(self, e)
        auto_battle_utils.resume_running(self.auto_op)

    def after_operation_done(self, result: OperationResult):
        ZOperation.after_operation_done(self, result)

        auto_battle_utils.stop_running(self.auto_op)