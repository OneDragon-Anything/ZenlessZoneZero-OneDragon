from one_dragon.base.operation.application.application_config import ApplicationConfig


class CloudQueueConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            module_name='cloud_queue',
            instance_idx=instance_idx,
            group_id=group_id,
        )

    @property
    def prefer_bangbang_points(self) -> bool:
        return self.get('prefer_bangbang_points', False)

    @prefer_bangbang_points.setter
    def prefer_bangbang_points(self, new_value: bool) -> None:
        self.update('prefer_bangbang_points', new_value)
