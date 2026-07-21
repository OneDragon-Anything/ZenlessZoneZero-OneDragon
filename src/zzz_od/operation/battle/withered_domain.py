"""枯萎之都战斗 op(shadow 基类节点 + 重定义特化节点 + 覆写 hook)。

从 ``hollow_zero/hollow_battle.py`` 复制 check_distance_to_move / _get_rid_of_stuck + 移动链 3 节点。
原 ``HollowBattle`` 不动(复制副本,后续切换 PR 再清理)。

op 边界:等战斗画面 → 判断特殊移动 → 特殊移动 → 向前移动(战前移动,距离驱动 + 6 方向脱困)→ 自动战斗(判断结束返回 status)。
波次间(auto_battle STATUS_NEED_MOVE → 下一个 op 的战前移动)/ 结束后(4 路由 + 失败链)交外层。
设计依据:docs/superpowers/specs/2026-07-21-battle-op-boundary-design.md。
"""
from typing import TYPE_CHECKING

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.battle.base import BattleOpBase

if TYPE_CHECKING:
    from cv2.typing import MatLike


class WitheredDomainBattleOp(BattleOpBase):
    """枯萎之都(原零号空洞)战斗 op。

    shadow 基类「战前移动」/「开始自动战斗」;
    重定义「判断特殊移动」/「特殊移动」/「向前移动」(含 6 方向脱困)/「自动战斗」;
    覆写 _check_battle_state(normal+hollow+check_distance) + _check_in_battle_secondary(with_distance>=5)。
    波次间 / 结束后(4 路由 + 失败链)交外层。
    """

    STATUS_DIRECT_BATTLE: str = '不需要移动'   # 判断特殊移动出口:直接开打
    STATUS_FAIL_TO_MOVE: str = '移动失败'      # 向前移动出口:脱困失败(op 返回,外层处理)

    def __init__(self, ctx: ZContext) -> None:
        """Args:
            ctx: ZContext。
        """
        BattleOpBase.__init__(self, ctx, op_name='枯萎之都 自动战斗')
        self.distance_pos: Rect | None = None              # 显示距离的区域(check_distance_to_move 更新)
        self.stuck_move_direction: int = 0                 # 受困时移动的方向(0..5,_get_rid_of_stuck 分支选择)
        self.last_distance: float | None = None            # 上次移动前的距离(受困判断)
        self.last_stuck_distance: float | None = None      # 上次受困显示的距离(脱困方向有效性判断)
        self.last_distance_to_turn: float | None = None    # 上次转向的距离(多距离去重,check_distance_to_move 读写)
        self.turn_times: int = 0                           # 转向次数(子类自管,基类不跟踪)

    # ===== shadow:移除基类「战前移动」/「开始自动战斗」节点 =====
    # 保留 start_auto_battle 方法体(check_special_move/move_to_battle 内部调)。

    def pre_battle_move(self) -> None:
        """shadow:移除基类「战前移动」节点(枯萎之都用「判断特殊移动」替代)。"""
        pass

    def start_auto_battle(self) -> None:
        """shadow:移除基类「开始自动战斗」节点,但保留方法体(供「判断特殊移动」/「向前移动」条件触发调用)。"""
        self.ctx.auto_battle_context.start_auto_battle()

    # ===== 重定义节点(移动链 3 节点 + auto_battle)=====

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='判断特殊移动')
    def check_special_move(self) -> OperationRoundResult:
        """识别距离:with_distance>=10 → STATUS_NEED_MOVE(→特殊移动);without_distance>=10 → 直接开打;否则等待。"""
        self.check_distance_to_move(self.last_screenshot)

        if self.ctx.auto_battle_context.with_distance_times >= 10:
            return self.round_success(BattleOpBase.STATUS_NEED_MOVE)
        if self.ctx.auto_battle_context.without_distance_times >= 10:
            self.start_auto_battle()
            return self.round_success(WitheredDomainBattleOp.STATUS_DIRECT_BATTLE)

        return self.round_wait()

    @node_from(from_name='判断特殊移动', status=BattleOpBase.STATUS_NEED_MOVE)
    @operation_node(name='特殊移动')
    def special_move(self) -> OperationRoundResult:
        """长按 W 1.5s 通过特殊移动门(release=True 显式释放)。"""
        self.ctx.controller.move_w(press=True, press_time=1.5, release=True)
        return self.round_success()

    @node_from(from_name='特殊移动')
    @operation_node(name='向前移动')
    def move_to_battle(self) -> OperationRoundResult:
        """距离驱动前移 + 6 方向脱困状态机(内联 turn/move,自管 turn_times;不用基类 _move_one_step)。

        5 分支:
        1. check_distance_to_move 更新 distance_pos + 计数器 + last_distance_to_turn。
        2. distance_pos None + without_distance>=10 → start_auto_battle + '返回战斗'(→自动战斗)。
        3. _move_times>=20 or turn_times>=60 → STATUS_FAIL_TO_MOVE(op 失败,外层处理)。
        4. 受困(距离没变)→ 切脱困方向 + _get_rid_of_stuck。
        5. 正常 → 偏离转向 / 否则按距离 press_time 前移。
        """
        self.check_distance_to_move(self.last_screenshot)

        if self.distance_pos is None:
            if self.ctx.auto_battle_context.without_distance_times >= 10:
                self.start_auto_battle()
                return self.round_success(status='返回战斗')
            return self.round_wait(wait=0.02)

        if self._move_times >= 20 or self.turn_times >= 60:
            # 移动比较久也没到 → op 失败(外层处理退出)
            return self.round_fail(WitheredDomainBattleOp.STATUS_FAIL_TO_MOVE)

        current_distance = self.ctx.auto_battle_context.last_check_distance
        if self.last_distance is not None and abs(self.last_distance - current_distance) < 0.5:
            log.info('上次移动后距离没有发生变化 尝试脱困')
            if self.last_stuck_distance is not None and abs(self.last_stuck_distance - current_distance) < 0.5:
                # 困的时候显示的距离跟上次困住的一样 代表脱困方向不对 换一个
                log.info('上次脱困后距离没有发生变化 更换脱困方向')
                self.stuck_move_direction = (self.stuck_move_direction + 1) % 6

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
            press_time = self.ctx.auto_battle_context.last_check_distance / 7.2  # 朱鸢测出来的速度
            self.ctx.controller.move_w(press=True, press_time=press_time, release=True)
            self._move_times += 1
            self.last_distance_to_turn = None  # 移动完后重新识别
            return self.round_wait(wait=0.5)

    @node_from(from_name='判断特殊移动', status=STATUS_DIRECT_BATTLE)
    @node_from(from_name='向前移动', status='返回战斗')
    @operation_node(name='自动战斗', mute=True, timeout_seconds=600)
    def auto_battle(self) -> OperationRoundResult:
        """重定义;入口重置 _move_times + turn_times → 透传基类 auto_battle(判断结束返回 status)。
        _check_in_battle_secondary(with_distance>=5 → STATUS_NEED_MOVE)= 波次间,op 返回,外层调下一个 op。"""
        self._move_times = 0
        self.turn_times = 0
        return super().auto_battle()

    # ===== hook 覆写 =====

    def _get_auto_battle_op_name(self) -> str | None:
        """用 challenge_config.auto_battle(对齐原 hollow_battle.py:58)。"""
        return self.ctx.withered_domain.challenge_config.auto_battle

    def _check_battle_state(self) -> bool:
        """开 normal + hollow + check_distance(对齐原 hollow_battle.py:180-185)。"""
        return self.ctx.auto_battle_context.check_battle_state(
            self.last_screenshot, self.last_screenshot_time,
            check_battle_end_normal_result=True, check_battle_end_hollow_result=True, check_distance=True,
        )

    def _check_in_battle_secondary(self, in_battle: bool) -> str | None:
        """with_distance_times>=5 → STATUS_NEED_MOVE(波次间,op 返回;外层调下一个 op 的战前移动)。"""
        if self.ctx.auto_battle_context.with_distance_times >= 5:
            return BattleOpBase.STATUS_NEED_MOVE
        return None

    # move_to_battle 内联 turn/move,不用基类 _move_one_step(自管 turn_times)

    # ===== 从 hollow_battle.py 复制(check_distance_to_move / _get_rid_of_stuck)=====
    # 复制自 src/zzz_od/hollow_zero/hollow_battle.py:280-287,143-164(签名/实现照原)。

    def check_distance_to_move(self, screen: 'MatLike') -> None:
        """[复制自 hollow_battle.py:280-287] 同步调 check_battle_distance,更新 distance_pos + last_distance_to_turn。"""
        mr = self.ctx.auto_battle_context.check_battle_distance(screen, self.last_distance_to_turn)

        if mr is None:
            self.distance_pos = None
        else:
            self.distance_pos = mr.rect
            self.last_distance_to_turn = mr.data

    def _get_rid_of_stuck(self) -> None:
        """[复制自 hollow_battle.py:143-164] 6 方向脱困状态机(0..5;由调用方切方向,本方法只执行移动)。"""
        log.info(f'本次脱困方向 {self.stuck_move_direction}')
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
