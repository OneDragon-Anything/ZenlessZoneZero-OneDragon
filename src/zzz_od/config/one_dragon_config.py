from one_dragon.base.config.one_dragon_config import OneDragonConfig


class ZOneDragonConfig(OneDragonConfig):
    """绝区零的一条龙全局配置。"""

    @property
    def game_settings_profile_enabled(self) -> bool:
        return self.get("game_settings_profile_enabled", False)

    @game_settings_profile_enabled.setter
    def game_settings_profile_enabled(self, new_value: bool) -> None:
        self.update("game_settings_profile_enabled", new_value)

    @property
    def game_settings_profile_run_path(self) -> str:
        return self.get("game_settings_profile_run_path", "")

    @game_settings_profile_run_path.setter
    def game_settings_profile_run_path(self, new_value: str) -> None:
        self.update("game_settings_profile_run_path", new_value)

    @property
    def game_settings_profile_normal_path(self) -> str:
        return self.get("game_settings_profile_normal_path", "")

    @game_settings_profile_normal_path.setter
    def game_settings_profile_normal_path(self, new_value: str) -> None:
        self.update("game_settings_profile_normal_path", new_value)
