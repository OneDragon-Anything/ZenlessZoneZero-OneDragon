from enum import Enum
from typing import ClassVar

from one_dragon.base.config.config_item import ConfigItem
from zzz_od.application.hollow_zero.hollow_period_speed import hollow_period_speed_const
from zzz_od.application.hollow_zero.withered_domain.withered_domain_config import (
    HollowZeroExtraExitEnum,
    HollowZeroExtraTask,
    WitheredDomainConfig,
)
from zzz_od.hollow_zero.hollow_zero_challenge_config import (
    HollowZeroChallengeConfig,
    HollowZeroChallengePathFinding,
)


class HollowPeriodSpeedGoal(Enum):

    EVA_POINT = ConfigItem('刷满业绩')
    PERIOD_REWARD = ConfigItem('刷满丁尼')  # 丁尼即枯萎之都里的周期奖励


class HollowPeriodSpeedConfig(WitheredDomainConfig):

    MISSION_NAME: ClassVar[str] = '施工废墟-内部'  # 固定进入的副本

    def __init__(self, instance_idx: int, group_id: str):
        WitheredDomainConfig.__init__(
            self,
            instance_idx=instance_idx,
            group_id=group_id,
            app_id=hollow_period_speed_const.APP_ID,
        )

    @property
    def mission_name(self) -> str:
        return HollowPeriodSpeedConfig.MISSION_NAME

    @property
    def weekly_plan_times(self) -> int:
        # 没有基础次数的要求 直接按周期奖励刷取
        return 0

    @property
    def goal(self) -> str:
        return self.get('goal', HollowPeriodSpeedGoal.PERIOD_REWARD.value.value)

    @goal.setter
    def goal(self, new_value: str):
        self.update('goal', new_value)

    @property
    def extra_task(self) -> str:
        # 刷取目标对应枯萎之都里的额外刷取 共用运行记录和停止条件的判断
        if self.goal == HollowPeriodSpeedGoal.EVA_POINT.value.value:
            return HollowZeroExtraTask.EVA_POINT.value.value
        return HollowZeroExtraTask.PERIOD_REWARD.value.value

    @property
    def extra_exit(self) -> str:
        return HollowZeroExtraExitEnum.LEVEL_3_EVA.value.value

    @property
    def target_agents(self) -> list[str | None]:
        return self.get('target_agents', [None, None, None])

    @target_agents.setter
    def target_agents(self, new_value: list[str | None]):
        self.update('target_agents', new_value)

    @property
    def auto_battle(self) -> str:
        return self.get('auto_battle', '全配队通用')

    @auto_battle.setter
    def auto_battle(self, new_value: str):
        self.update('auto_battle', new_value)

    def build_challenge_config(self) -> HollowZeroChallengeConfig:
        """
        只需要代理人和自动战斗 其余使用默认值 mock 配置不会写入文件
        """
        challenge_config = HollowZeroChallengeConfig('', is_mock=True)
        challenge_config.auto_battle = self.auto_battle
        challenge_config.target_agents = self.target_agents
        challenge_config.path_finding = HollowZeroChallengePathFinding.ONLY_BOSS.value.value
        return challenge_config
