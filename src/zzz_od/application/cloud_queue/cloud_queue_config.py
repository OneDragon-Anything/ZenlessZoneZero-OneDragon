from typing import Optional

from one_dragon.base.config.yaml_config import YamlConfig


class CloudQueueConfig(YamlConfig):

    def __init__(self, instance_idx: Optional[int] = None):
        YamlConfig.__init__(
            self,
            module_name='cloud_queue',
            instance_idx=instance_idx,
        )

    @property
    def prefer_bangbang_points(self) -> bool:
        return self.get('prefer_bangbang_points', False)

    @prefer_bangbang_points.setter
    def prefer_bangbang_points(self, new_value: bool) -> None:
        self.update('prefer_bangbang_points', new_value)
