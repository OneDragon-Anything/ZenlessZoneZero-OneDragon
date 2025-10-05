
from one_dragon.base.operation.application.application_config import ApplicationConfig


class WorldPatrolConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id='world_patrol',
            instance_idx=instance_idx,
            group_id=group_id,
        )

    @property
    def auto_battle(self) -> str:
        return self.get('auto_battle', '全配队通用')

    @auto_battle.setter
    def auto_battle(self, new_value: str) -> None:
        self.update('auto_battle', new_value)

    @property
    def route_list(self) -> str:
        return self.get('route_list', '')

    @route_list.setter
    def route_list(self, new_value: str) -> None:
        self.update('route_list', new_value)