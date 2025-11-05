import time
from concurrent.futures import Future
from typing import Tuple, Union

from cv2.typing import MatLike

from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.application.shiyu_defense.agent_selector import get_best_agent_for_moving
from zzz_od.application.zzz_application import ZApplication
from zzz_od.auto_battle.auto_battle_dodge_context import YoloStateEventEnum
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum, CommonAgentStateEnum
from zzz_od.operation.zzz_operation import ZOperation


def load_auto_op(op: Union[ZOperation, ZApplication], auto_config_sub_dir: str, auto_config_name: str) -> OperationRoundResult:
    """
    加载自动战斗指令
    :param op:
    :param auto_config_sub_dir:
    :param auto_config_name:
    :return:
    """
    if op.auto_op is not None:  # 如果有上一个 先销毁
        op.auto_op.dispose()
    op.auto_op = AutoBattleOperator(op.ctx, auto_config_sub_dir, auto_config_name)
    success, msg = op.auto_op.init_before_running()
    if not success:
        return op.round_fail(msg)

    return op.round_success()


def load_auto_op_async(op: Union[ZOperation, ZApplication], auto_config_sub_dir: str, auto_config_name: str) -> Future[Tuple[bool, str]]:
    if op.auto_op is not None:  # 如果有上一个 先销毁
        op.auto_op.dispose()
    op.auto_op = AutoBattleOperator(op.ctx, auto_config_sub_dir, auto_config_name)
    return op.auto_op.init_before_running_async()


def stop_running(auto_op: AutoBattleOperator) -> None:
    """
    停止自动战斗
    """
    if auto_op is not None:
        auto_op.stop_running()


def resume_running(auto_op: AutoBattleOperator) -> None:
    """
    继续自动战斗
    """
    if auto_op is not None:
        auto_op.start_running_async()


def switch_to_best_agent_for_moving(auto_op: AutoBattleOperator, timeout_seconds: float = 5) -> None:
    """
    切换到最适合移动的角色
    :param auto_op:
    :param timeout_seconds:
    :return:
    """
    start_time = time.time()
    while True:
        now = time.time()
        if now - start_time >= timeout_seconds:
            break

        screenshot_time, screenshot = auto_op.ctx.controller.screenshot()
        auto_op.auto_battle_context.agent_context.check_agent_related(screenshot, screenshot_time)
        team_info = auto_op.auto_battle_context.agent_context.team_info
        if team_info is None or len(team_info.agent_list) == 0:
            time.sleep(0.2)
            continue

        best_agent = get_best_agent_for_moving(team_info)
        if best_agent is None:
            time.sleep(0.2)
            continue

        # 如果最佳角色就是当前角色，则无需切换
        if (
            len(team_info.agent_list) > 0
            and team_info.agent_list[0].agent is not None
            and team_info.agent_list[0].agent.agent_id == best_agent.agent.agent_id
        ):
            break

        auto_op.auto_battle_context.switch_by_name(best_agent.agent.agent_name)
        time.sleep(0.2)


def check_battle_encounter(auto_op: AutoBattleOperator, screen: MatLike, screenshot_time: float) -> bool:
    """
    判断是否进入了战斗
    1. 识别角色血量扣减
    2. 识别黄光红光
    @param screen: 游戏截图
    @param screenshot_time: 截图时间
    @return: 是否进入了战斗
    """
    if auto_op is None:
        return False

    in_battle = auto_op.auto_battle_context.is_normal_attack_btn_available(screen)
    if in_battle:
        auto_op.auto_battle_context.agent_context.check_agent_related(screen, screenshot_time)
        state = auto_op.get_state_recorder(CommonAgentStateEnum.LIFE_DEDUCTION_31.value.state_name)
        if state is not None and state.last_record_time == screenshot_time:
            return True

        auto_op.auto_battle_context.dodge_context.check_dodge_flash(screen, screenshot_time)
        state = auto_op.get_state_recorder(YoloStateEventEnum.DODGE_RED.value)
        if state is not None and state.last_record_time == screenshot_time:
            return True
        state = auto_op.get_state_recorder(YoloStateEventEnum.DODGE_YELLOW.value)
        if state is not None and state.last_record_time == screenshot_time:
            return True

    return False


def check_battle_encounter_in_period(ctx: ZContext, auto_op: AutoBattleOperator, total_check_seconds: float) -> bool:
    """
    持续一段时间检测是否进入战斗
    @param total_check_seconds: 总共检测的秒数
    @return:
    """
    start = time.time()

    while True:
        screenshot_time = time.time()

        if screenshot_time - start >= total_check_seconds:
            return False

        screenshot_time, screen = ctx.controller.screenshot()
        if check_battle_encounter(auto_op, screen, screenshot_time):
            return True

        time.sleep(ctx.battle_assistant_config.screenshot_interval)