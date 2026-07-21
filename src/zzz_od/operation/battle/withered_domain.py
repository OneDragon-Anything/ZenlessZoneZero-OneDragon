"""枯萎之都战斗 op(shadow 基类节点 + 重定义特化节点 + 覆写 hook)。

从 ``hollow_zero/hollow_battle.py`` 复制 check_distance_to_move / _get_rid_of_stuck +
移动链 3 节点 + 4 路由 + 失败链。原 ``HollowBattle`` 不动(复制副本,后续切换 PR 再清理)。

设计依据:docs/superpowers/specs/2026-07-20-withered-domain-battle-op-design.md
(5 轮 review 收敛,逐行对照原 hollow_battle.py 验证)。
"""
import time
from typing import TYPE_CHECKING

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from zzz_od.application.hollow_zero.withered_domain import withered_domain_const
from zzz_od.application.hollow_zero.withered_domain.withered_domain_run_record import (
    WitheredDomainRunRecord,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.battle.base import BattleOpBase

if TYPE_CHECKING:
    from cv2.typing import MatLike


class WitheredDomainBattleOp(BattleOpBase):
    """枯萎之都(原零号空洞)战斗 op。

    shadow 基类「战前移动」/「开始自动战斗」/「战斗结束」(用 4 路由收尾,不用 ChooseNext);
    重定义「判断特殊移动」/「特殊移动」/「向前移动」(含 6 方向脱困)/「自动战斗」(back-edge)
    / 4 路由 / 失败链;
    覆写 _check_battle_state(normal+hollow+check_distance) + _check_in_battle_secondary(with_distance>=5)。
    """

    STATUS_DIRECT_BATTLE: str = '不需要移动'   # 判断特殊移动出口:直接开打(对齐 HollowBattle.STATUS_NO_NEED_SPECIAL_MOVE 同值)
    STATUS_FAIL_TO_MOVE: str = '移动失败'      # 向前移动出口:脱困失败

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
        self.run_record: WitheredDomainRunRecord | None = ctx.run_context.get_run_record(
            instance_idx=ctx.current_instance_idx, app_id=withered_domain_const.APP_ID,
        )

    # ===== shadow:移除基类「战前移动」/「开始自动战斗」/「战斗结束」节点 =====
    # 保留 start_auto_battle 方法体(check_special_move/move_to_battle 内部调);pre_battle_move/route_after_battle 空实现。

    def pre_battle_move(self) -> None:
        """shadow:移除基类「战前移动」节点(枯萎之都用「判断特殊移动」替代)。"""
        pass

    def start_auto_battle(self) -> None:
        """shadow:移除基类「开始自动战斗」节点,但保留方法体(供「判断特殊移动」/「向前移动」条件触发调用)。"""
        self.ctx.auto_battle_context.start_auto_battle()

    def route_after_battle(self) -> None:
        """shadow:移除基类「战斗结束」节点(枯萎之都用 4 路由收尾,不用 ChooseNext)。"""
        pass

    # ===== 重定义节点(移动链 3 节点 + auto_battle back-edge + 4 路由 + 失败链)=====

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
        """长按 W 1.5s 通过特殊移动门(清理原 if/else dead code 同支;release=True 显式释放)。"""
        self.ctx.controller.move_w(press=True, press_time=1.5, release=True)
        return self.round_success()

    @node_from(from_name='特殊移动')
    @node_from(from_name='自动战斗', status=BattleOpBase.STATUS_NEED_MOVE)
    @operation_node(name='向前移动')
    def move_to_battle(self) -> OperationRoundResult:
        """距离驱动前移 + 6 方向脱困状态机(内联 turn/move,自管 turn_times;不用基类 _move_one_step)。

        5 分支(spec §6.5):
        1. check_distance_to_move 更新 distance_pos + 计数器 + last_distance_to_turn。
        2. distance_pos None + without_distance>=10 → start_auto_battle + '返回战斗'(→自动战斗)。
        3. _move_times>=20 or turn_times>=60 → STATUS_FAIL_TO_MOVE(→移动失败)。
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
            # 移动比较久也没到 就自动退出了
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
        """重定义加 back-edge;入口重置 _move_times + turn_times(对齐原 :170-171)→ 透传基类 auto_battle。"""
        self._move_times = 0
        self.turn_times = 0
        return super().auto_battle()

    @node_from(from_name='自动战斗', status='零号空洞-结算周期上限')
    @operation_node(name='结算周期上限')
    def period_reward_full(self) -> OperationRoundResult:
        """结算周期上限:等待 + 标记奖励满 + 点确认。"""
        time.sleep(1)  # 第一次稍等等一段时间 避免按键还不能响应
        self.run_record.period_reward_complete = True
        return self.round_by_find_and_click_area(
            self.last_screenshot, '零号空洞-战斗', '结算周期上限-确认', success_wait=1, retry_wait=1)

    @node_from(from_name='结算周期上限')
    @node_from(from_name='自动战斗', status='零号空洞-挑战结果')
    @operation_node(name='战斗结果-确定')
    def after_battle(self) -> OperationRoundResult:
        """挑战结果确定:等 2s → 试结算周期上限确认(背景误识别兜底)→ OCR 点确定 → 兜底盲点。"""
        # 找到后稍微等待: 1.按钮刚出来的时候按不会有响应 2. 奖励列表可能还没有出现
        time.sleep(2)

        # 有时候可能会识别到背景上的挑战结果 这时候也尝试点
        result = self.round_by_find_and_click_area(self.last_screenshot, '零号空洞-战斗', '结算周期上限-确认')
        if result.is_success:
            return self.round_wait()  # 每次开始都有等待 这里就不等了

        area = self.ctx.screen_loader.get_area('零号空洞-战斗', '战斗结果-确定')
        result = self.round_by_ocr_and_click(self.last_screenshot, '确定', area=area)
        if result.is_success:
            return self.round_success(result.status, wait=1)

        # 匹配不到的时候 随便点击 防止有一些新的对话框出现没有处理到
        self.round_by_click_area('零号空洞-战斗', '战斗结果-确定')
        return self.round_retry(result.status, wait=1)

    @node_from(from_name='战斗结果-确定')
    @operation_node(name='更新楼层信息')
    def update_level_info(self) -> OperationRoundResult:
        """挑战结果确定后推进楼层信息(外层 HollowRunner 决定是否再开)。"""
        self.ctx.withered_domain.update_to_next_level()
        return self.round_success()

    @node_from(from_name='自动战斗', status='普通战斗-完成')
    @operation_node(name='普通战斗-完成')
    def mission_complete(self) -> OperationRoundResult:
        """普通战斗完成:检查丁尼奖励可见性 → 标记 period_reward_complete。"""
        # 在 battle_context 里会判断这个的出现
        # 找到后稍微等待: 1.按钮刚出来的时候按不会有响应 2. 奖励列表可能还没有出现
        time.sleep(2)
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '零号空洞-战斗', '通关-丁尼奖励')
        if not result.is_success:
            # 领满奖励了
            self.run_record.period_reward_complete = True
            self.save_screenshot()
        else:
            # 防止因为动画效果 奖励还没有出现 就出现了按钮
            self.run_record.period_reward_complete = False

        return self.round_success(status='普通战斗-完成')

    @node_from(from_name='自动战斗', status='普通战斗-撤退')
    @operation_node(name='战斗撤退')
    def battle_fail(self) -> OperationRoundResult:
        """战斗撤退:点撤退按钮。"""
        return self.round_by_find_and_click_area(
            self.last_screenshot, '战斗画面', '战斗结果-撤退', success_wait=1, retry_wait=1)

    @node_from(from_name='自动战斗', success=False, status=Operation.STATUS_TIMEOUT)
    @node_from(from_name='向前移动', success=False, status=STATUS_FAIL_TO_MOVE)
    @operation_node(name='移动失败')
    def move_fail(self) -> OperationRoundResult:
        """移动失败(向前移动 FAIL_TO_MOVE / 自动战斗 TIMEOUT 双入口):停战斗 + 找退出按钮 / 兜底开菜单。"""
        self.ctx.auto_battle_context.stop_auto_battle()

        result = self.round_by_find_area(self.last_screenshot, '零号空洞-战斗', '退出战斗')
        if result.is_success:
            return self.round_success(wait=0.5)  # 稍微等一下让按钮可按

        return self.round_by_click_area('战斗画面', '菜单', success_wait=1, retry_wait=1)

    @node_from(from_name='移动失败')
    @operation_node(name='点击退出')
    def click_exit(self) -> OperationRoundResult:
        """点退出战斗按钮。"""
        return self.round_by_find_and_click_area(
            self.last_screenshot, '零号空洞-战斗', '退出战斗', success_wait=1, retry_wait=1)

    @node_from(from_name='点击退出')
    @operation_node(name='点击退出确认')
    def click_exit_confirm(self) -> OperationRoundResult:
        """点退出战斗确认按钮。"""
        return self.round_by_find_and_click_area(
            self.last_screenshot, '零号空洞-战斗', '退出战斗-确认', success_wait=1, retry_wait=1)

    @node_from(from_name='点击退出确认')
    @operation_node(name='等待退出', node_max_retry_times=20)
    def wait_exit(self) -> OperationRoundResult:
        """等通关-完成画面出现(20 次重试)。"""
        return self.round_by_find_area(
            self.last_screenshot, '零号空洞-事件', '通关-完成',
            success_wait=2, retry_wait=1)  # 找到后稍微等待 按钮刚出来的时候按没有用

    # ===== hook 覆写(spec §6.2)=====

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
        """with_distance_times>=5 → STATUS_NEED_MOVE(回「向前移动」,对齐原 hollow_battle.py:176-178)。"""
        if self.ctx.auto_battle_context.with_distance_times >= 5:
            return BattleOpBase.STATUS_NEED_MOVE
        return None

    # _detect_move_target 不覆写(move_to_battle 内联 turn/move,不用基类 _move_one_step → 不调此 hook;
    # 基类默认返 None 即可,避免 dead code;spec §6.2 M1)

    # ===== 从 hollow_battle.py 复制(check_distance_to_move / _get_rid_of_stuck)=====
    # 整段复制自 src/zzz_od/hollow_zero/hollow_battle.py:280-287,143-164(签名/实现照原;原方法无前导下划线)。

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
