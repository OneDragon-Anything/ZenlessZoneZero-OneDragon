
from one_dragon.base.operation.application.application_config import ApplicationConfig

RANDOM_AGENT_NAME = '随机'

class RandomPlayConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id='random_play',
            instance_idx=instance_idx,
            group_id=group_id,
        )

    @property
    def agent_name_1(self) -> str:
        return self.get('agent_name_1', RANDOM_AGENT_NAME)

    @agent_name_1.setter
    def agent_name_1(self, new_value: str) -> None:
        self.update('agent_name_1', new_value)

    @property
    def agent_name_2(self) -> str:
        return self.get('agent_name_2', RANDOM_AGENT_NAME)

    @agent_name_2.setter
    def agent_name_2(self, new_value: str) -> None:
        self.update('agent_name_2', new_value)
