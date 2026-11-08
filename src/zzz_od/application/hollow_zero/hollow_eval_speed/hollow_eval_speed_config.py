from typing import ClassVar

from zzz_od.application.hollow_zero.hollow_eval_speed import hollow_eval_speed_const
from zzz_od.application.hollow_zero.withered_domain.withered_domain_config import (
    HollowZeroExtraExitEnum,
    HollowZeroExtraTask,
    WitheredDomainConfig,
)
from zzz_od.hollow_zero.hollow_zero_challenge_config import (
    HollowZeroChallengeConfig,
    HollowZeroChallengePathFinding,
)


class HollowEvalSpeedConfig(WitheredDomainConfig):

    MISSION_NAME: ClassVar[str] = '施工废墟-内部'  # 固定进入的副本

    def __init__(self, instance_idx: int, group_id: str):
        WitheredDomainConfig.__init__(
            self,
            instance_idx=instance_idx,
            group_id=group_id,
            app_id=hollow_eval_speed_const.APP_ID,
        )

    @property
    def mission_name(self) -> str:
        return HollowEvalSpeedConfig.MISSION_NAME

    @property
    def weekly_plan_times(self) -> int:
        # 没有基础次数的要求 直接刷业绩
        return 0

    @property
    def extra_task(self) -> str:
        # 目标固定为刷满业绩 共用枯萎之都的运行记录和停止条件的判断
        return HollowZeroExtraTask.EVA_POINT.value.value

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
