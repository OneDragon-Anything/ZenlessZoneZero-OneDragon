from __future__ import annotations

import time
from typing import TYPE_CHECKING

from cv2.typing import MatLike

from zzz_od.application.shiyu_defense.agent_selector import get_best_agent_for_moving
from zzz_od.auto_battle.auto_battle_dodge_context import YoloStateEventEnum
from zzz_od.game_data.agent import CommonAgentStateEnum

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


def switch_to_best_agent_for_moving(ctx: ZContext, timeout_seconds: float = 5) -> None:
    """
    切换到最适合移动的角色

    Args:
        ctx: 上下文
        timeout_seconds: 切换超时时间
    """
    start_time = time.time()
    while True:
        now = time.time()
        if now - start_time >= timeout_seconds:
            break

        screenshot_time, screenshot = ctx.controller.screenshot()
        ctx.auto_battle_context.agent_context.check_agent_related(screenshot, screenshot_time)
        team_info = ctx.auto_battle_context.agent_context.team_info
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

        ctx.auto_battle_context.switch_by_name(best_agent.agent.agent_name)
        time.sleep(0.2)

def check_battle_encounter(ctx: ZContext, screen: MatLike, screenshot_time: float) -> bool:
    """
    判断是否进入了战斗
    1. 识别角色血量扣减
    2. 识别黄光红光
    @param screen: 游戏截图
    @param screenshot_time: 截图时间
    @return: 是否进入了战斗
    """
    in_battle = ctx.auto_battle_context.is_normal_attack_btn_available(screen)
    state_record_service = ctx.auto_battle_context.state_record_service
    if in_battle:
        ctx.auto_battle_context.agent_context.check_agent_related(screen, screenshot_time)
        state = state_record_service.get_state_recorder(CommonAgentStateEnum.LIFE_DEDUCTION_31.value.state_name)
        if state is not None and state.last_record_time == screenshot_time:
            return True

        ctx.auto_battle_context.dodge_context.check_dodge_flash(screen, screenshot_time)
        state = state_record_service.get_state_recorder(YoloStateEventEnum.DODGE_RED.value)
        if state is not None and state.last_record_time == screenshot_time:
            return True
        state = state_record_service.get_state_recorder(YoloStateEventEnum.DODGE_YELLOW.value)
        if state is not None and state.last_record_time == screenshot_time:
            return True

    return False


def check_battle_encounter_in_period(ctx: ZContext, total_check_seconds: float) -> bool:
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
        if check_battle_encounter(ctx, screen, screenshot_time):
            return True

        time.sleep(ctx.battle_assistant_config.screenshot_interval)