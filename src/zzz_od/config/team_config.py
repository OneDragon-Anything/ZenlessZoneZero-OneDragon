from typing import List, Optional

from one_dragon.base.config.user_config import UserConfig
from zzz_od.game_data.agent import Agent


class PredefinedTeamInfo:

    def __init__(self, idx: int, name: str, auto_battle: str, agent_id_list: List[str]):
        self.idx: int = idx  # 在编队数组里的下标
        self.name: str = name  # 编队名称
        self.agent_id_list: List[str] = [i for i in agent_id_list]  # 代理人ID列表
        while len(self.agent_id_list) < 3:
            self.agent_id_list.append('unknown')
        self.auto_battle: str = auto_battle  # 对应的自动战斗配置


class TeamConfig(UserConfig):

    def __init__(self, instance_idx: int):
        UserConfig.__init__(self, 'team', instance_idx=instance_idx)

    @property
    def team_list(self) -> List[PredefinedTeamInfo]:
        data_list = self.get('team_list', [])

        max_cnt: int = 10
        team_list: List[PredefinedTeamInfo] = []
        for i in range(len(data_list)):
            data = data_list[i]
            team_list.append(PredefinedTeamInfo(i,
                                                name=data.get('name', f'编队{i+1}'),
                                                auto_battle=data.get('auto_battle', '全配队通用'),
                                                agent_id_list=data.get('agent_id_list', ['unknown', 'unknown', 'unknown']),
                                                ))

        current_cnt = len(team_list)
        for i in range(current_cnt + 1, max_cnt + 1):
            team_list.append(PredefinedTeamInfo(i-1, f'编队{i}', '全配队通用', []))

        return team_list

    def update_team(self, team_info: PredefinedTeamInfo) -> None:
        """
        更新一个配队
        """
        team_list = self.team_list
        if team_info.idx >= len(self.team_list):
            return

        team_list[team_info.idx] = team_info
        data_team_list = [
            {
                'name': team_info.name,
                'auto_battle': team_info.auto_battle,
                'agent_id_list': team_info.agent_id_list,
            } for team_info in team_list
        ]

        self.update('team_list', data_team_list)

    def get_team_by_idx(self, team_idx: int) -> Optional[PredefinedTeamInfo]:
        """
        根据下标获取预备配队
        @param team_idx:
        @return:
        """
        for team in self.team_list:
            if team.idx == team_idx:
                return team
        return None

    def update_team_members(self, team_name: str, members: List[Agent]) -> None:
        """
        更新某个配队的代理人
        @param team_name: 配队名称
        @param members: 代理人列表
        @return:
        """
        for team in self.team_list:
            if team.name == team_name:
                agent_id_list = [i.agent_id for i in members]
                while len(agent_id_list) < 3:
                    agent_id_list.append('unknown')
                team.agent_id_list = agent_id_list
                self.update_team(team)
                break
