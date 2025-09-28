from typing import Optional

from one_dragon.base.config.user_config import UserConfig


class WorldPatrolConfig(UserConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        UserConfig.__init__(
            self,
            module_name='world_patrol',
            instance_idx=instance_idx,
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
