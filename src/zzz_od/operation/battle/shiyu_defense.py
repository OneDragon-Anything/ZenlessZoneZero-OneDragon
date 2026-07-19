"""式舆防卫战战斗 op(shadow 基类节点 + 重定义特化节点 + 覆写 hook)。

从 ``application/shiyu_defense/shiyu_defense_battle.py`` 复制 check_distance/check_teleport_point/
check_shiyu_countdown + start_move/move_after_battle 逻辑。原 ShiyuDefenseBattle 不动。

设计依据:docs/superpowers/specs/2026-07-20-battle-op-base-design.md §8。
"""
from typing import TYPE_CHECKING

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.auto_battle.auto_battle_utils import switch_to_best_agent_for_moving
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.battle.base import BattleOpBase, MoveTarget
from zzz_od.operation.challenge_mission.exit_in_battle import ExitInBattle

if TYPE_CHECKING:
    from cv2.typing import MatLike


class ShiyuDefenseBattleOp(BattleOpBase):
    """式舆防卫战战斗 op。

    shadow 基类「战前移动」/「开始自动战斗」(防卫战用「开始移动」循环 + start_auto_battle 内嵌条件触发);
    重定义「开始移动」/「自动战斗」(加 back-edge)/「战斗后移动」/「战斗结束」/「战斗超时」;
    覆写 _check_battle_state(normal+defense) + _check_in_battle_secondary(倒计时副判)。
    """

    _move_after_battle_times_limit: int = 60    # move_after_battle 的 _move_times 上限(对齐原 shiyu_defense_battle.py:224;start_move 用基类 _move_times_limit=20)

    def __init__(self, ctx: ZContext, predefined_team_idx: int) -> None:
        """Args:
            ctx: ZContext。
            predefined_team_idx: 预备编队下标(必传)。
        """
        BattleOpBase.__init__(self, ctx, op_name='式舆防卫战 自动战斗', predefined_team_idx=predefined_team_idx)
        self.team_config: PredefinedTeamInfo | None = ctx.team_config.get_team_by_idx(predefined_team_idx)
        self.distance_pos: Rect | None = None    # 复制原 ShiyuDefenseBattle op 属性(check_distance 更新)

    # ===== shadow:移除基类「战前移动」/「开始自动战斗」节点(保留 start_auto_battle 方法体)=====

    def pre_battle_move(self) -> None:
        """shadow:移除基类「战前移动」节点(防卫战用「开始移动」替代)。"""
        pass

    def start_auto_battle(self) -> None:
        """shadow:移除基类「开始自动战斗」节点,但保留方法体(供「开始移动」条件触发调用)。"""
        self.ctx.auto_battle_context.start_auto_battle()

    # ===== 重定义节点 =====

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='开始移动')
    def start_move(self) -> OperationRoundResult:
        """战前移动循环:倒计时出现→进战斗;否则距离驱动移动;距离持续失败→兜底开战。"""
        now = self.last_screenshot_time
        if now - self._last_countdown_check_time >= 1:    # 倒计时节流(每 1s,有意新增减压,spec §8.1)
            self._last_countdown_check_time = now
            if self.check_shiyu_countdown(self.last_screenshot):
                self.start_auto_battle()
                self._move_times = 0
                return self.round_success(status='返回战斗')
        self.check_distance(self.last_screenshot)
        if self.distance_pos is not None:
            self._move_one_step(MoveTarget(pos=self.distance_pos.center,
                                           distance=self.ctx.auto_battle_context.last_check_distance,
                                           source='distance'), cap=4)
        elif self.ctx.auto_battle_context.without_distance_times >= 10:
            # 距离持续失败 10 次 → 直接开战(对齐原 :71-77)
            self.start_auto_battle()
            self._move_times = 0
            return self.round_success(status='返回战斗')
        else:
            return self.round_wait(wait=0.02)                          # 纯等待,不盲转(对齐原)
        if self._move_times >= self._move_times_limit:
            return self.round_by_op_result(
                ExitInBattle(self.ctx, '式舆防卫战', '前哨档案').execute())
        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='开始移动', status='返回战斗')
    @node_from(from_name='战斗后移动', status='返回战斗')
    @operation_node(name='自动战斗', mute=True, timeout_seconds=600)
    def auto_battle(self) -> OperationRoundResult:
        """重定义加 back-edge;直接透传基类 auto_battle 的 OperationRoundResult(不包 round_by_op_result)。"""
        return super().auto_battle()

    @node_from(from_name='自动战斗', status=BattleOpBase.STATUS_NEED_MOVE)
    @operation_node(name='战斗后移动')
    def move_after_battle(self) -> OperationRoundResult:
        """战后移动:countdown 重现回战斗 / 交互键进下一层 / 无普攻+无交互→阶段胜利 / 否则 switch+移动。"""
        if self.check_shiyu_countdown(self.last_screenshot):
            self.start_auto_battle()                # 倒计时重现 → 重启 auto_battle 后台脚本(对齐原 :163-169)
            self._move_times = 0
            self._no_countdown_start_time = None
            return self.round_success(status='返回战斗')
        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
        if result.is_success:
            self.ctx.controller.interact(press=True, press_time=0.2, release=True)
            return self.round_wait(wait=0.5)
        normal = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击')
        if not normal.is_success:
            return self.round_success(status=BattleOpBase.STATUS_TO_NEXT_PHASE)   # 阶段胜利
        # 确认要移动 → switch + detect + move(switch 放这,对齐原 line 180「确认移动前」)
        switch_to_best_agent_for_moving(self.ctx)
        target = self._detect_move_target()
        self._move_one_step(target, cap=1)    # target None → _on_no_target 盲转(基类处理,spec §8.1 三层)
        if self._move_times >= self._move_after_battle_times_limit:
            return self.round_by_op_result(
                ExitInBattle(self.ctx, '式舆防卫战', '前哨档案').execute())
        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='自动战斗', status='战斗结束-撤退')
    @node_from(from_name='自动战斗', status='战斗结束-退出')
    @operation_node(name='战斗结束')
    def route_after_battle(self) -> OperationRoundResult:
        """按 last_check_end_result status 分流:撤退/退出点对应 area。战斗结束-下一防线是 area(由 app 处理)。"""
        status = self.ctx.auto_battle_context.last_check_end_result
        if status == '战斗结束-撤退':
            return self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战', '战斗结束-撤退', success_wait=1, retry_wait=1)
        if status == '战斗结束-退出':
            return self.round_by_find_and_click_area(self.last_screenshot, '式舆防卫战', '战斗结束-退出', success_wait=1, retry_wait=1)
        return self.round_success(status=status)

    @node_from(from_name='自动战斗', success=False, status=Operation.STATUS_TIMEOUT)
    @operation_node(name='战斗超时')
    def battle_timeout(self) -> OperationRoundResult:
        """auto_battle 连续 600s 未结束 → 退到前哨档案(对齐原 ShiyuDefenseBattle battle_timeout→voluntary_exit→wait_exit 等前哨档案)。"""
        return self.round_by_op_result(
            ExitInBattle(self.ctx, '式舆防卫战', '前哨档案').execute())

    # ===== hook 覆写 =====

    def _get_auto_battle_op_name(self) -> str | None:
        """防卫战用 team_config.auto_battle(对齐原 shiyu_defense_battle.py:51)。"""
        return self.team_config.auto_battle if self.team_config else None

    def _check_battle_state(self) -> bool:
        """开 normal + defense(防卫战结算 area)。"""
        return self.ctx.auto_battle_context.check_battle_state(
            self.last_screenshot, self.last_screenshot_time,
            check_battle_end_normal_result=True, check_battle_end_defense_result=True)

    def _check_in_battle_secondary(self, in_battle: bool) -> str | None:
        """倒计时连续 5s 无(战斗中)/ 交互键连续 10 次(非战斗中) → STATUS_NEED_MOVE。"""
        now = self.last_screenshot_time
        if in_battle:
            if now - self._last_countdown_check_time >= 1:
                self._last_countdown_check_time = now
                if self.check_shiyu_countdown(self.last_screenshot):
                    self._no_countdown_start_time = None
                else:
                    if self._no_countdown_start_time is None:
                        self._no_countdown_start_time = now
                    if now - self._no_countdown_start_time >= 5:
                        return BattleOpBase.STATUS_NEED_MOVE
        else:
            self._no_countdown_start_time = None
            r = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
            self._find_interact_btn_times = self._find_interact_btn_times + 1 if r.is_success else 0
            if self._find_interact_btn_times >= 10:
                return BattleOpBase.STATUS_NEED_MOVE
        return None

    def _detect_move_target(self) -> MoveTarget | None:
        """三层目标:距离 → 传送点 → None(无目标,move_after_battle 走 _on_no_target)。"""
        self.check_distance(self.last_screenshot)
        if self.distance_pos is not None:
            return MoveTarget(pos=self.distance_pos.center,
                              distance=self.ctx.auto_battle_context.last_check_distance, source='distance')
        rect = self.check_teleport_point(self.last_screenshot)
        if rect is not None:
            return MoveTarget(pos=rect.center, distance=None, source='teleport')
        return None

    # ===== 从原 ShiyuDefenseBattle 复制(check_distance / check_shiyu_countdown / check_teleport_point)=====
    # 整段复制自 src/zzz_od/application/shiyu_defense/shiyu_defense_battle.py:230,238,259(签名/实现照原;原方法无前导下划线)。

    def check_distance(self, screen: 'MatLike') -> None:
        """[复制自 shiyu_defense_battle.py:230] 同步调 check_battle_distance,更新 distance_pos。"""
        mr = self.ctx.auto_battle_context.check_battle_distance(screen)

        if mr is None:
            self.distance_pos = None
        else:
            self.distance_pos = mr.rect

    def check_shiyu_countdown(self, screen: 'MatLike') -> bool:
        """[复制自 shiyu_defense_battle.py:238] 防卫战倒计时 pipeline(4 contours=有倒计时)。"""
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

    def check_teleport_point(self, screen: 'MatLike') -> Rect | None:
        """[复制自 shiyu_defense_battle.py:259] 防卫战空洞传送点 pipeline。"""
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
