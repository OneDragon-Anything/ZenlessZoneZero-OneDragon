from typing import Optional, ClassVar

from cv2.typing import MatLike

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
        self.distance_pos: Optional[Rect] = None  # 显示距离的区域
        self.move_times: int = 0  # 移动次数
        self.battle_fail: Optional[str] = None  # 战斗失败的原因
        self.find_interact_btn_times: int = 0  # 发现交互按钮的次数
        self.no_countdown_start_time: Optional[float] = None  # 连续没有倒计时的开始时间戳

    @operation_node(name='加载自动战斗指令', is_start_node=True)
    def load_auto_op(self) -> OperationRoundResult:
        self.ctx.auto_battle_context.init_auto_op(
            sub_dir='auto_battle',
            op_name=self.ctx.battle_assistant_config.auto_battle if self.team_config is None else self.team_config.auto_battle,
        )
        return self.round_success()

    @node_from(from_name='加载自动战斗指令')
    @operation_node(name='等待战斗画面加载', node_max_retry_times=60)
    def wait_battle_screen(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击', retry_wait_round=1)
        return result

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='向前移动准备战斗')
    def start_move(self):
        # 在移动阶段也检测倒计时，一旦检测到倒计时就停止移动开始战斗
        if self.check_shiyu_countdown(self.last_screenshot):
            self.ctx.auto_battle_context.start_auto_battle()
            self.move_times = 0
            return self.round_success()
        self.check_distance(self.last_screenshot)

        if self.distance_pos is None:
            if self.ctx.auto_battle_context.without_distance_times >= 10:
                self.ctx.auto_battle_context.start_auto_battle()
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
            press_time = self.ctx.auto_battle_context.last_check_distance / 7.2  # 朱鸢测出来的速度
            # 有可能识别错距离 设置一个最大的移动时间
            press_time = min(press_time, 4)
            self.ctx.controller.move_w(press=True, press_time=press_time, release=True)
            self.move_times += 1
            return self.round_wait(wait=0.5)

    @node_from(from_name='向前移动准备战斗')
    @node_from(from_name='战斗后移动', status='返回战斗')
    @operation_node(name='自动战斗', timeout_seconds=600, mute=True)
    def auto_battle(self) -> OperationRoundResult:
        if self.ctx.auto_battle_context.last_check_end_result is not None:
            self.ctx.auto_battle_context.stop_auto_battle()
            return self.round_success(status=self.ctx.auto_battle_context.last_check_end_result)

        in_battle = self.ctx.auto_battle_context.check_battle_state(
            self.last_screenshot, self.last_screenshot_time,
            check_battle_end_normal_result=True,
            check_battle_end_defense_result=True,
            check_distance=False)

        if in_battle:
            # 在战斗中检测倒计时状态
            current_time = self.last_screenshot_time

            # 每1秒检测一次倒计时
            if not hasattr(self, '_last_countdown_check_time'):
                self._last_countdown_check_time = 0

            if current_time - self._last_countdown_check_time < 1:
                # 还没到检测间隔
                return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

            # 执行倒计时检测
            self._last_countdown_check_time = current_time
            if self.check_shiyu_countdown(self.last_screenshot):
                # 有倒计时，重置连续时间记录
                self.no_countdown_start_time = None
            else:
                # 没有倒计时
                if self.no_countdown_start_time is None:
                    # 第一次检测到没有倒计时，记录连续期间的开始时间
                    self.no_countdown_start_time = current_time
                else:
                    # 已经在连续没有倒计时的期间，检查从开始到现在的时间差
                    time_diff = current_time - self.no_countdown_start_time

                    # 连续5秒没有倒计时才认定战斗结束
                    if time_diff >= 5.0:
                        self.no_countdown_start_time = None
                        self.ctx.auto_battle_context.stop_auto_battle()
                        return self.round_success(status=ShiyuDefenseBattle.STATUS_NEED_SPECIAL_MOVE)
        else:
            # 不在战斗画面，重置连续没有倒计时的时间记录
            self.no_countdown_start_time = None
            result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
            if result.is_success:
                self.find_interact_btn_times += 1
            else:
                self.find_interact_btn_times = 0

            if self.find_interact_btn_times >= 10:
                self.ctx.auto_battle_context.stop_auto_battle()
                return self.round_success(status=ShiyuDefenseBattle.STATUS_NEED_SPECIAL_MOVE)

        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='自动战斗', status=STATUS_NEED_SPECIAL_MOVE)
    @operation_node(name='战斗后移动', node_max_retry_times=5)
    def move_after_battle(self) -> OperationRoundResult:
        # 在战斗后移动阶段也检测倒计时，如果检测到倒计时则返回战斗中
        if self.check_shiyu_countdown(self.last_screenshot):
            # 重新启动自动战斗
            self.ctx.auto_battle_context.start_auto_battle()
            # 重置移动次数和连续无倒计时记录
            self.move_times = 0
            self.no_countdown_start_time = None
            return self.round_success(status='返回战斗')

        result1 = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
        if result1.is_success:
            self.ctx.controller.interact(press=True, press_time=0.2, release=True)
            return self.round_wait(result1.status, wait=0.5)

        result2 = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击')
        if not result2.is_success:
            # 交互和普通攻击都没有找到 说明战斗胜利了
            return self.round_success(ShiyuDefenseBattle.STATUS_TO_NEXT_PHASE)
        auto_battle_utils.switch_to_best_agent_for_moving(self.ctx)  # 移动前切换到最佳角色

        # 多层检测机制 - 统一的转向和前进逻辑
        target_pos = None
        target_type = None
        move_distance = None

        # 第1层：检测距离
        self.check_distance(self.last_screenshot)
        if self.distance_pos is not None:
            target_pos = self.distance_pos.center
            target_type = "距离显示"
            move_distance = self.ctx.auto_battle_context.last_check_distance

        # 第2层：检测传送点
        if target_pos is None:
            teleport_rect = self.check_teleport_point(self.last_screenshot)
            if teleport_rect is not None:
                target_pos = teleport_rect.center
                target_type = "传送点"
                move_distance = 5.0  # 传送点固定移动5米

        # 第3层：盲动转向
        if target_pos is None:
            if not hasattr(self, '_blind_turn_direction'):
                self._blind_turn_direction = 1  # 1=右转，-1=左转

            self.ctx.controller.turn_by_distance(self._blind_turn_direction * 200)  # 统一使用200像素
            return self.round_wait(wait=0.5)

        # 统一的转向和前进逻辑
        screen_center_x = self.ctx.project_config.screen_standard_width // 2
        target_x = target_pos.x
        deviation = target_x - screen_center_x

        if abs(deviation) > 50:  # 偏差大于50像素需要转向
            self.ctx.controller.turn_by_distance(50 if deviation > 0 else -50)
        else:
            # 目标在屏幕中心，前进
            if move_distance is not None:
                press_time = move_distance / 7.2  # 朱鸢测出来的速度
                if press_time > 1:  # 不要移动太久
                    press_time = 1

                self.ctx.controller.move_w(press=True, press_time=press_time, release=True)
                self.move_times += 1

        return self.round_wait(wait=0.5)

        if self.move_times >= 60:
            self.battle_fail = ShiyuDefenseBattle.STATUS_FAIL_TO_MOVE
            return self.round_fail(ShiyuDefenseBattle.STATUS_FAIL_TO_MOVE)

    def check_distance(self, screen: MatLike) -> None:
        mr = self.ctx.auto_battle_context.check_battle_distance(screen)

        if mr is None:
            self.distance_pos = None
        else:
            self.distance_pos = mr.rect

    def check_shiyu_countdown(self, screen: MatLike) -> bool:
        """
        检查防卫战倒计时状态
        :param screen: 屏幕截图
        :return: True表示有倒计时（战斗继续），False表示没有倒计时（战斗结束）
        """
        try:
            # 检测普通倒计时
            result1 = self.ctx.cv_service.run_pipeline('防卫战倒计时', screen, timeout=1.0)
            has_countdown1 = result1 is not None and result1.is_success and len(result1.contours) == 4
            
            # 检测精英倒计时
            result2 = self.ctx.cv_service.run_pipeline('防卫战倒计时-精英', screen, timeout=1.0)
            has_countdown2 = result2 is not None and result2.is_success and len(result2.contours) == 4
            
            # 只要有一个倒计时被检测到，就认为有倒计时
            return has_countdown1 or has_countdown2

        except Exception:
            return False

    def check_teleport_point(self, screen: MatLike) -> Optional[Rect]:
        """
        检测防卫战空洞传送点
        :param screen: 屏幕截图
        :return: 传送点的矩形区域，找不到返回None
        """
        try:
            result = self.ctx.cv_service.run_pipeline('防卫战空洞传送点', screen, timeout=1.0)

            if result is None or not result.is_success:
                return None

            rect_pairs = result.get_absolute_rect_pairs()

            if len(rect_pairs) > 0:
                max_pair = max(rect_pairs, key=lambda pair: len(pair[0]))
                _, (x1, y1, x2, y2) = max_pair
                return Rect(x1, y1, x2, y2)
            else:
                return None

        except Exception:
            return None

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
        self.ctx.auto_battle_context.stop_auto_battle()
        result = self.round_by_find_area(self.last_screenshot, '式舆防卫战', '退出战斗')
        if result.is_success:
            return self.round_success(wait=0.5)  # 稍微等一下让按钮可按

        return self.round_by_click_area('战斗画面', '菜单',
                                        success_wait=1, retry_wait=1)

    @node_from(from_name='主动退出')
    @operation_node(name='点击退出')
    def click_exit(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战', '退出战斗',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击退出')
    @operation_node(name='点击退出确认')
    def click_exit_confirm(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(self.last_screenshot, '零号空洞-战斗', '退出战斗-确认',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='自动战斗', status='战斗结束-撤退')
    @operation_node(name='战斗失败撤退')
    def battle_fail_exit(self) -> OperationRoundResult:
        self.battle_fail = '战斗结束-撤退'
        return self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战', '战斗结束-撤退',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击退出确认')
    @node_from(from_name='战斗失败撤退')
    @operation_node(name='等待退出', node_max_retry_times=60)
    def wait_exit(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '式舆防卫战', '街区')

        if result.is_success:
            if self.battle_fail is None:
                return self.round_success(result.status)
            else:
                return self.round_fail(self.battle_fail)

        return self.round_retry(result.status, wait=1)

    def handle_pause(self, e=None):
        self.ctx.auto_battle_context.stop_auto_battle()

    def handle_resume(self, e=None):
        if self.current_node.node is not None and self.current_node.node.cn == '自动战斗':
            self.ctx.auto_battle_context.resume_auto_battle()
