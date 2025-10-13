from typing import Optional

from zzz_od.auto_battle.auto_battle_agent_context import TeamInfo, AgentInfo
from zzz_od.game_data.agent import Agent, AgentEnum, AgentTypeEnum


def get_best_agent_for_moving(team_info: TeamInfo) -> Optional[AgentInfo]:
    """
    从队伍中获取最适合移动的角色
    :param team_info:
    :return:
    """
    if team_info is None or len(team_info.agent_list) == 0:
        return None

    best_agent: Optional[AgentInfo] = None
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
    # 安比, 猫又, 可琳, 珂蕾妲, 苍角, 露西, 青衣, 艾莲, 派派, 橘福福
    if agent.agent_id in ['anby', 'nekomata', 'corin', 'koleda', 'soukaku', 'lucy', 'qingyi', 'ellen', 'piper', 'ju_fufu']:
        return 0
    # 雅, 仪玄, 青衣, 比利, 猫又, 熊
    if agent.agent_id in ['hoshimi_miyabi', 'yixuan', 'qingyi', 'billy', 'nekomata', 'ben', 'panyinhu']:
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