from typing import List

from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.game_data.agent import DmgTypeEnum


class ShiyuDefenseTeamConfig:

    def __init__(self, team_idx: int, weakness_list: List[DmgTypeEnum], for_critical: bool = False):
        """
        式舆防卫战的配队配置
        @param team_idx:
        @param weakness_list:
        """
        self.team_idx: int = team_idx
        self.for_critical: bool = for_critical  # 参与剧变节点
        self.weakness_list: List[DmgTypeEnum] = weakness_list  # 应付弱点


class ShiyuDefenseConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id='shiyu_defense',
            instance_idx=instance_idx,
            group_id=group_id,
        )

        self.team_list: List[ShiyuDefenseTeamConfig] = []

        self.init_team_list()

    def init_team_list(self) -> None:
        """
        初始化配队配置
        @return:
        """
        self.team_list = []
        team_list = self.get('team_list', [])
        for team_data in team_list:
            team_idx = team_data.get('team_idx', -1)
            for_critical = team_data.get('for_critical', False)
            weakness_list = team_data.get('weakness_list', [])

            team_config = ShiyuDefenseTeamConfig(
                team_idx,
                [DmgTypeEnum.from_name(i) for i in weakness_list],
                for_critical
            )
            self.team_list.append(team_config)

    def save_team_list(self) -> None:
        """
        保存配队配置
        @return:
        """
        team_list_data = []

        for team_config in self.team_list:
            team_data = {
                'team_idx': team_config.team_idx,
                'for_critical': team_config.for_critical,
                'weakness_list': [i.name for i in team_config.weakness_list],
            }
            team_list_data.append(team_data)

        self.data['team_list'] = team_list_data
        self.save()

    def get_config_by_team_idx(self, team_idx: int) -> ShiyuDefenseTeamConfig:
        """
        根据编队下标获取对应弱点
        """
        for config in self.team_list:
            if config.team_idx == team_idx:
                return config

        new_config = ShiyuDefenseTeamConfig(team_idx, [])
        self.team_list.append(new_config)
        return new_config

    def add_weakness(self, team_idx: int, dmg_type: DmgTypeEnum) -> None:
        """
        增加弱点
        """
        team_config = self.get_config_by_team_idx(team_idx)
        if team_config is None:
            return

        if dmg_type in team_config.weakness_list:  # 已经存在 就不变更了
            return

        team_config.weakness_list.append(dmg_type)
        self.save_team_list()

    def remove_weakness(self, team_idx: int, dmg_type: DmgTypeEnum) -> None:
        """
        移除弱点
        """
        team_config = self.get_config_by_team_idx(team_idx)
        if team_config is None:
            return

        if dmg_type not in team_config.weakness_list:  # 不存在 就不变更了
            return

        team_config.weakness_list.remove(dmg_type)
        self.save_team_list()

    def change_for_critical(self, team_idx: int, for_critical: bool) -> None:
        """
        修改是否参与剧变节点
        """
        team_config = self.get_config_by_team_idx(team_idx)
        if team_config is None:
            return

        if team_config.for_critical == for_critical:
            return

        team_config.for_critical = for_critical
        self.save_team_list()

    @property
    def critical_max_node_idx(self) -> int:
        return self.get('critical_max_node_idx', 7)

    @critical_max_node_idx.setter
    def critical_max_node_idx(self, value: int) -> None:
        self.update('critical_max_node_idx', value)