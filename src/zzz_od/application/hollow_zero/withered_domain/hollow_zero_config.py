from enum import Enum

from typing import Optional

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.user_config import UserConfig
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class HollowZeroExtraTask(Enum):

    NONE = ConfigItem('不进行')
    EVA_POINT = ConfigItem('刷满业绩点')
    PERIOD_REWARD = ConfigItem('刷满周期奖励')


class HollowZeroExtraExitEnum(Enum):

    COMPLETE = ConfigItem('通关')
    LEVEL_2_EVA = ConfigItem('2层业绩后退出')
    LEVEL_3_EVA = ConfigItem('3层业绩后退出')


class HollowZeroConfig(UserConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        UserConfig.__init__(
            self,
            module_name='hollow_zero',
            instance_idx=instance_idx,
        )

    @property
    def mission_name(self) -> str:
        return self.get('mission_name', '旧都列车-内部')

    @mission_name.setter
    def mission_name(self, new_value: str):
        self.update('mission_name', new_value)

    @property
    def challenge_config(self) -> str:
        return self.get('challenge_config', '默认-专属空洞-艾莲')

    @challenge_config.setter
    def challenge_config(self, new_value: str):
        self.update('challenge_config', new_value)

    @property
    def challenge_config_adapter(self) -> YamlConfigAdapter:
        return YamlConfigAdapter(self, 'challenge_config', '默认-专属空洞-艾莲')

    @property
    def weekly_plan_times(self) -> int:
        return self.get('weekly_plan_times', 2)

    @weekly_plan_times.setter
    def weekly_plan_times(self, new_value: int):
        self.update('weekly_plan_times', new_value)

    @property
    def daily_plan_times(self) -> int:
        return self.get('daily_plan_times', 99)

    @daily_plan_times.setter
    def daily_plan_times(self, new_value: int):
        self.update('daily_plan_times', new_value)

    @property
    def extra_task(self) -> str:
        return self.get('extra_task', HollowZeroExtraTask.PERIOD_REWARD.value.value)

    @extra_task.setter
    def extra_task(self, new_value: str):
        self.update('extra_task', new_value)

    @property
    def extra_exit(self) -> str:
        return self.get('extra_exit', HollowZeroExtraExitEnum.COMPLETE.value.value)

    @extra_exit.setter
    def extra_exit(self, new_value: str):
        self.update('extra_exit', new_value)
