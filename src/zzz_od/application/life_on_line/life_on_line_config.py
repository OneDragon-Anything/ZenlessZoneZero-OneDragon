from typing import Optional

from one_dragon.base.config.user_config import UserConfig
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class LifeOnLineConfig(UserConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        UserConfig.__init__(
            self,
            module_name='life_on_line',
            instance_idx=instance_idx,
        )

    @property
    def daily_plan_times(self) -> int:
        return self.get('daily_plan_times', 20)

    @daily_plan_times.setter
    def daily_plan_times(self, new_value: int) -> None:
        self.update('daily_plan_times', new_value)

    @property
    def predefined_team_idx(self) -> int:
        """
        预备编队
        -1 = 游戏内配队
        :return:
        """
        return self.get('predefined_team_idx', -1)

    @predefined_team_idx.setter
    def predefined_team_idx(self, new_value: int) -> None:
        self.update('predefined_team_idx', new_value)

    @property
    def predefined_team_idx_adapter(self) -> YamlConfigAdapter:
        return YamlConfigAdapter(self, 'predefined_team_idx', -1)
