from typing import Optional

from one_dragon.base.config.yaml_config import YamlConfig


class RandomPlayConfig(YamlConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        YamlConfig.__init__(
            self,
            module_name='random_play',
            instance_idx=instance_idx,
        )

    @staticmethod
    def random_agent_name() -> str:
        return '随机'

    @property
    def agent_name_1(self) -> str:
        return self.get('agent_name_1', self.random_agent_name())

    @agent_name_1.setter
    def agent_name_1(self, new_value: str) -> None:
        self.update('agent_name_1', new_value)

    @property
    def agent_name_2(self) -> str:
        return self.get('agent_name_2', self.random_agent_name())

    @agent_name_2.setter
    def agent_name_2(self, new_value: str) -> None:
        self.update('agent_name_2', new_value)
