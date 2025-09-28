from typing import Optional

from one_dragon.base.config.user_config import UserConfig


class RandomPlayConfig(UserConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        UserConfig.__init__(
            self,
            module_name='random_play',
            instance_idx=instance_idx,
        )

    @staticmethod
    def random_agent_name() -> str:
        return '随机'

    @property
    def agent_name_1(self) -> float:
        return self.get('agent_name_1', self.random_agent_name())

    @agent_name_1.setter
    def agent_name_1(self, new_value: float) -> None:
        self.update('agent_name_1', new_value)

    @property
    def agent_name_2(self) -> float:
        return self.get('agent_name_2', self.random_agent_name())

    @agent_name_2.setter
    def agent_name_2(self, new_value: float) -> None:
        self.update('agent_name_2', new_value)
