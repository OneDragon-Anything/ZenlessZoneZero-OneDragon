"""战斗 op 基类:固定节点扛朴素共性 + hook 承特化差异。

子类:
- NormalBattleOp:纯继承基类节点图(朴素 normal 战斗)。
- ShiyuDefenseBattleOp:shadow 不要的基类节点 + 重定义特化节点 + 覆写 hook。

设计依据:docs/superpowers/specs/2026-07-20-battle-op-base-design.md。
"""
from dataclasses import dataclass

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.challenge_mission.check_next_after_battle import (
    ChooseNextOrFinishAfterBattle,
)
from zzz_od.operation.zzz_operation import ZOperation


@dataclass
class MoveTarget:
    """移动目标(战前 / 战后移动通用)。

    Attributes:
        pos: 目标屏幕坐标(``_move_one_step`` 用 pos.x 判偏离中心)。
        distance: OCR 距离(算 move_w press_time);None=无距离(用默认步长)。
        source: 来源标识('distance'/'teleport'/'detector'/...),便于调试。
    """
    pos: Point
    distance: float | None
    source: str


class BattleOpBase(ZOperation):
    """战斗 op 基类。

    固定节点图(朴素类线性流,NormalBattleOp 纯继承):
    加载自动战斗指令 → 等待战斗画面加载 → 战前移动 → 开始自动战斗 → 自动战斗 → 战斗结束。

    特化类(ShiyuDefenseBattleOp)shadow 不要的基类节点 + 重定义特化节点 + 覆写 hook。
    基类不感知 ``check_battle_state`` 的 flag 参数空间(子类自调,见 ``_check_battle_state``)。
    """

    STATUS_NEED_MOVE: str = '需要移动'        # 一层清完需移动(复用 ShiyuDefenseBattle.STATUS_NEED_SPECIAL_MOVE 同值同义)
    STATUS_NEXT_LEVEL: str = '进入下层'       # 外层递归实例化(迷失之地式)
    STATUS_COMPLETE: str = '通关'             # 整场结束
    STATUS_TO_NEXT_PHASE: str = '下一阶段'    # 防卫战阶段胜利(交外层)

    # 类属性(子类可覆写)
    _auto_battle_sub_dir: str | None = 'auto_battle'
    _interact_as_wait_fallback: bool = False
    _turn_threshold_px: int = 50
    _turn_step_px: int = 50
    _move_press_time_cap: float = 4.0
    _default_move_distance: float = 5.0
    _blind_turn_step: int = 200
    _move_times_limit: int = 20

    def __init__(self, ctx: ZContext, op_name: str = '战斗',
                 auto_battle_config: str = '全配队通用', predefined_team_idx: int = -1,
                 try_next: bool = False, is_agent_plan: bool = False) -> None:
        """通用参数。

        Args:
            ctx: ZContext。
            op_name: op 显示名(避免 display_name='指令[ ]')。
            auto_battle_config: 自动战斗脚本名(predefined_team_idx==-1 时用)。
            predefined_team_idx: 预备编队下标;-1=不指定(用 auto_battle_config)。
            try_next: 战斗结束后是否「再来一次」(ChooseNextOrFinishAfterBattle 入参)。
            is_agent_plan: 是否代理人计划(ChooseNextOrFinishAfterBattle 入参)。
        """
        ZOperation.__init__(self, ctx, op_name=op_name)
        self.auto_battle_config: str = auto_battle_config
        self.predefined_team_idx: int = predefined_team_idx
        self._try_next: bool = try_next
        self._is_agent_plan: bool = is_agent_plan
        self._move_times: int = 0
        self._no_countdown_start_time: float | None = None
        self._find_interact_btn_times: int = 0
        self._last_countdown_check_time: float = 0
        self._screen_center_x: int = ctx.project_config.screen_standard_width // 2

    # ===== 固定节点(NormalBattleOp 纯继承)=====

    @operation_node(name='加载自动战斗指令', is_start_node=True)
    def load_auto_op(self) -> OperationRoundResult:
        """加载自动战斗脚本(op_name=None → 跳过,外层已注入)。"""
        op_name = self._get_auto_battle_op_name()
        if op_name is not None:
            self.ctx.auto_battle_context.init_auto_op(sub_dir=self._auto_battle_sub_dir, op_name=op_name)
        return self.round_success()

    @node_from(from_name='加载自动战斗指令')
    @operation_node(name='等待战斗画面加载', node_max_retry_times=60)
    def wait_battle_screen(self) -> OperationRoundResult:
        """等「战斗画面/按键-普通攻击」(可选「按键-交互」fallback)。"""
        result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-普通攻击', retry_wait_round=1)
        if result.is_success:
            return self.round_success()
        if self._interact_as_wait_fallback:
            result = self.round_by_find_area(self.last_screenshot, '战斗画面', '按键-交互')
            if result.is_success:
                return self.round_success()
        return self.round_retry(result.status, wait=1)

    @node_from(from_name='等待战斗画面加载')
    @operation_node(name='战前移动')
    def pre_battle_move(self) -> OperationRoundResult:
        """战前默认前移(朴素类 typical;特化类覆写/shadow)。"""
        self.ctx.controller.move_w(press=True, press_time=1, release=True)
        return self.round_success()

    @node_from(from_name='战前移动')
    @operation_node(name='开始自动战斗')
    def start_auto_battle(self) -> OperationRoundResult:
        """启动 auto_battle 后台脚本。"""
        self.ctx.auto_battle_context.start_auto_battle()
        return self.round_success()

    @node_from(from_name='开始自动战斗')
    @operation_node(name='自动战斗', mute=True, timeout_seconds=600)
    def auto_battle(self) -> OperationRoundResult:
        """自动战斗主循环(一轮)。"""
        return self._do_auto_battle_round()

    @node_from(from_name='自动战斗')
    @operation_node(name='战斗结束')
    def route_after_battle(self) -> OperationRoundResult:
        """战斗后收尾(默认 ChooseNextOrFinishAfterBattle;特化类覆写)。"""
        return self.round_by_op_result(
            ChooseNextOrFinishAfterBattle(self.ctx, try_next=self._try_next, is_agent_plan=self._is_agent_plan).execute())

    # ===== 主循环一轮 =====

    def _do_auto_battle_round(self) -> OperationRoundResult:
        """auto_battle 节点一轮逻辑(基类普通方法,被 ``auto_battle`` 节点调;子类重定义 auto_battle 时 ``return super().auto_battle()`` 复用)。"""
        ctx = self.ctx.auto_battle_context
        if ctx.last_check_end_result is not None:                 # ① 上一轮异步 _check_battle_end 写入的结束 area(可能滞后一轮,原代码亦然)
            ctx.stop_auto_battle()
            return self.round_success(status=ctx.last_check_end_result)
        in_battle = self._check_battle_state()                    # ② hook:子类自调 ctx.check_battle_state(传自己的 flag),基类不感知 flag
        sec = self._check_in_battle_secondary(in_battle)          # ③ 战中副判
        if sec is not None:
            ctx.stop_auto_battle()
            return self.round_success(status=sec)                 # 如 STATUS_NEED_MOVE
        return self.round_wait(wait=self.ctx.battle_assistant_config.screenshot_interval)

    # ===== Hook(模板方法,子类覆写)=====

    def _get_auto_battle_op_name(self) -> str | None:
        """返回自动战斗脚本名(None=外层已注入,跳过 init)。子类必须覆写。"""
        raise NotImplementedError('子类必须提供 auto_battle 脚本名')

    def _check_battle_state(self) -> bool:
        """调 ``ctx.check_battle_state`` 返 in_battle。默认只 normal;子类按需加其他 flag(基类不感知 flag 参数空间)。"""
        return self.ctx.auto_battle_context.check_battle_state(
            self.last_screenshot, self.last_screenshot_time,
            check_battle_end_normal_result=True)

    def _check_in_battle_secondary(self, in_battle: bool) -> str | None:
        """战中副判(如防卫战倒计时 / 迷失之地 detector)。默认 None(无副判)。"""
        return None

    # ===== 辅助方法(特化类移动复用)=====

    def _detect_move_target(self) -> MoveTarget | None:
        """检测移动目标。默认 None(不移动);特化类覆写。"""
        return None

    def _move_one_step(self, target: MoveTarget | None, cap: float | None = None) -> None:
        """按目标移动一步(turn 偏离 / move_w press_time=distance/7.2 capped)。target=None → _on_no_target 盲转。"""
        if target is None:
            self._on_no_target()
            return
        deviation = target.pos.x - self._screen_center_x
        if abs(deviation) > self._turn_threshold_px:
            self.ctx.controller.turn_by_distance(self._turn_step_px if deviation > 0 else -self._turn_step_px)
        else:
            press_time = (target.distance or self._default_move_distance) / 7.2
            press_time = min(press_time, cap if cap is not None else self._move_press_time_cap)
            self.ctx.controller.move_w(press=True, press_time=press_time, release=True)
        self._move_times += 1

    def _on_no_target(self) -> None:
        """无目标盲转(防卫战距离/传送点都没找到的兜底)。"""
        self.ctx.controller.turn_by_distance(-self._blind_turn_step)

    # ===== pause/resume 回调(非节点,框架 _on_pause/_on_resume 调)=====

    def handle_pause(self, e=None) -> None:
        """暂停 → 停 auto_battle。"""
        self.ctx.auto_battle_context.stop_auto_battle()

    def handle_resume(self, e=None) -> None:
        """恢复 → 若在自动战斗节点,resume auto_battle。"""
        if self.current_node.node is not None and self.current_node.node.cn == '自动战斗':
            self.ctx.auto_battle_context.resume_auto_battle()
