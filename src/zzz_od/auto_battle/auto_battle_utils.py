from __future__ import annotations

import time
from typing import TYPE_CHECKING

from cv2.typing import MatLike

from zzz_od.auto_battle.auto_battle_dodge_context import YoloStateEventEnum
from zzz_od.game_data.agent import AgentTypeEnum, CommonAgentStateEnum

if TYPE_CHECKING:
    from zzz_od.auto_battle.auto_battle_agent_context import AgentInfo, TeamInfo
    from zzz_od.context.zzz_context import ZContext
    from zzz_od.game_data.agent import Agent


def _get_best_agent_for_moving(team_info: TeamInfo) -> AgentInfo | None:
    """
    从队伍中获取最适合移动的角色
    :param team_info:
    :return:
    """
    if team_info is None or len(team_info.agent_list) == 0:
        return None

    best_agent: AgentInfo | None = None
    best_priority = 99

    for team_agent_info in team_info.agent_list:
        agent = team_agent_info.agent
        if agent is None:
            continue

        priority = _get_agent_priority(agent)

        if priority < best_priority:
            best_priority = priority
            best_agent = team_agent_info

    return best_agent


def _get_agent_priority(agent: Agent) -> int:
    """
    获取角色的优先级
    身高不会挡住传送点的同时，速度越慢越好
    :param agent:
    :return:
    """
    # -- 特殊角色判断 --
    # 耀嘉音
    if agent.agent_id == 'astra_yao':
        return 5
    # 安比, 猫又, 可琳, 珂蕾妲, 苍角, 露西, 青衣, 派派, 橘福福, 琉音
    if agent.agent_id in ['anby', 'nekomata', 'corin', 'koleda', 'soukaku', 'lucy', 'qingyi', 'piper', 'ju_fufu', 'dialyn']:
        return 0
    # 雅, 仪玄, 比利, 熊, 照
    if agent.agent_id in ['hoshimi_miyabi', 'yixuan', 'billy', 'ben', 'panyinhu', 'zhao']:
        return 4

    # -- 类型判断 --
    # 支援
    if agent.agent_type == AgentTypeEnum.SUPPORT:
        return 1
    # 防护
    if agent.agent_type == AgentTypeEnum.DEFENSE:
        return 2

    # -- 其他 --
    return 3


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

        best_agent = _get_best_agent_for_moving(team_info)
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
