from __future__ import annotations

from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import (
    LostVoidChallengeConfig,
)
from zzz_od.application.matrix_action import matrix_action_const


class MatrixActionConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id=matrix_action_const.APP_ID,
            instance_idx=instance_idx,
            group_id=group_id,
        )

    @property
    def daily_plan_times(self) -> int:
        return self.get("daily_plan_times", 5)

    @daily_plan_times.setter
    def daily_plan_times(self, new_value: int) -> None:
        self.update("daily_plan_times", new_value)

    @property
    def weekly_plan_times(self) -> int:
        return self.get("weekly_plan_times", 2)

    @weekly_plan_times.setter
    def weekly_plan_times(self, new_value: int) -> None:
        self.update("weekly_plan_times", new_value)

    @property
    def challenge_config(self) -> str:
        return self.get("challenge_config", "默认-成就模式")

    @challenge_config.setter
    def challenge_config(self, new_value: str) -> None:
        self.update("challenge_config", new_value)

    @property
    def team_name(self) -> str:
        return self.get("team_name", "编队1")

    @team_name.setter
    def team_name(self, new_value: str) -> None:
        self.update("team_name", new_value)

    @property
    def challenge_config_instance(self) -> LostVoidChallengeConfig:
        return LostVoidChallengeConfig(self.challenge_config)
