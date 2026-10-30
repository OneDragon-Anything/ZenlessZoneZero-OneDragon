from one_dragon.base.config.yaml_config import YamlConfig


class StandaloneAppConfig(YamlConfig):
    """独立应用运行界面的配置"""

    def __init__(self, instance_idx: int):
        YamlConfig.__init__(self, 'standalone_app', instance_idx=instance_idx)

    @property
    def app_list(self) -> list[str]:
        return self.get('app_list', [])

    @app_list.setter
    def app_list(self, new_value: list[str]) -> None:
        self.update('app_list', new_value)

    @property
    def active_app_id(self) -> str:
        return self.get('active_app_id', '')

    @active_app_id.setter
    def active_app_id(self, new_value: str) -> None:
        self.update('active_app_id', new_value)
