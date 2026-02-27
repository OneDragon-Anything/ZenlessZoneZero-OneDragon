from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.application.intel_board import intel_board_const


class IntelBoardConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id=intel_board_const.APP_ID,
            instance_idx=instance_idx,
            group_id=group_id,
        )

    @property
    def predefined_team_idx(self) -> int:
        """预备编队下标，-1 代表不选择"""
        return self.get('predefined_team_idx', -1)

    @predefined_team_idx.setter
    def predefined_team_idx(self, new_value: int) -> None:
        self.update('predefined_team_idx', new_value)

    @property
    def auto_battle_config(self) -> str:
        """自动战斗配置名称"""
        return self.get('auto_battle_config', '全配队通用')

    @auto_battle_config.setter
    def auto_battle_config(self, new_value: str) -> None:
        self.update('auto_battle_config', new_value)

    @property
    def exp_grind_mode(self) -> bool:
        """是否开启刷满经验模式，开启后按经验值判断完成而非情报板进度"""
        return self.get('exp_grind_mode', False)

    @exp_grind_mode.setter
    def exp_grind_mode(self, new_value: bool) -> None:
        self.update('exp_grind_mode', new_value)
