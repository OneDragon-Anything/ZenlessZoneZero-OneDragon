from enum import Enum
from typing import Optional

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig


class GamePlatformEnum(Enum):

    PC = ConfigItem('PC')


class GameLanguageEnum(Enum):

    CN = ConfigItem('简体中文', 'cn')
    EN = ConfigItem('English', 'en')


class GameRegionEnum(Enum):

    CN = ConfigItem('国服/B服', 'cn')
    AMERICA = ConfigItem('美服', 'us')
    EUROPE = ConfigItem('欧服', 'eu')
    ASIA = ConfigItem('亚服', 'asia')
    TWHKMO = ConfigItem('港澳台服', 'twhkmo')


class GameAccountConfig(YamlConfig):

    def __init__(self, instance_idx: int):
        YamlConfig.__init__(self, 'game_account', instance_idx=instance_idx)

    @property
    def platform(self) -> str:
        return self.get('platform', GamePlatformEnum.PC.value.value)

    @platform.setter
    def platform(self, new_value: str) -> None:
        self.update('platform', new_value)

    @property
    def game_region(self) -> str:
        return self.get('game_region', GameRegionEnum.CN.value.value)

    @game_region.setter
    def game_region(self, new_value: str) -> None:
        self.update('game_region', new_value)

    @property
    def use_custom_win_title(self) -> bool:
        return self.get('use_custom_win_title', False)

    @use_custom_win_title.setter
    def use_custom_win_title(self, new_value: bool) -> None:
        self.update('use_custom_win_title', new_value)

    @property
    def custom_win_title(self) -> str:
        return self.get('custom_win_title', '')

    @custom_win_title.setter
    def custom_win_title(self, new_value: str) -> None:
        self.update('custom_win_title', new_value)

    @property
    def game_path(self) -> str:
        return self.get('game_path', '')

    @game_path.setter
    def game_path(self, new_value: str) -> None:
        self.update('game_path', new_value)

    @property
    def game_language(self) -> str:
        return self.get('game_language', GameLanguageEnum.CN.value.value)

    @game_language.setter
    def game_language(self, new_value: str) -> None:
        self.update('game_language', new_value)

    @property
    def account(self) -> str:
        return self.get('account', '')

    @account.setter
    def account(self, new_value: str) -> None:
        self.update('account', new_value)

    @property
    def password(self) -> str:
        return self.get('password', '')

    @password.setter
    def password(self, new_value: str) -> None:
        self.update('password', new_value)

    @property
    def game_refresh_hour_offset(self) -> int:
        if self.game_region == GameRegionEnum.CN.value.value:
            return 4
        elif self.game_region == GameRegionEnum.AMERICA.value.value:
            return -9
        elif self.game_region == GameRegionEnum.EUROPE.value.value:
            return -3
        elif self.game_region == GameRegionEnum.ASIA.value.value:
            return 4
        elif self.game_region == GameRegionEnum.TWHKMO.value.value:
            return 4
        return 4
