from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig


class GamePlatformEnum(Enum):

    PC = ConfigItem('PC')


class GameLanguageEnum(Enum):

    CN = ConfigItem('简体中文', 'cn')
    EN = ConfigItem('English', 'en')


class GameRegionEnum(Enum):

    CN = ConfigItem('国服', 'cn')
    CNB = ConfigItem('B服', 'cn_b')
    AMERICA = ConfigItem('美服', 'us')
    EUROPE = ConfigItem('欧服', 'eu')
    ASIA = ConfigItem('亚服', 'asia')
    TWHKMO = ConfigItem('港澳台服', 'twhkmo')


class GameAccountConfig(YamlConfig):

    def __init__(self, instance_idx: int):
        YamlConfig.__init__(self, 'game_account', instance_idx=instance_idx)

    @classmethod
    def is_different_game_path(cls, current_idx: int, next_idx: int) -> bool:
        """
        判断两个实例配置的游戏路径是否不同
        """
        current_game_path = cls(current_idx).game_path
        next_game_path = cls(next_idx).game_path
        return bool(current_game_path and next_game_path and current_game_path != next_game_path)

    @classmethod
    def has_multi_instance_same_client(cls, current_idx: int, instance_indices: list[int]) -> bool:
        """
        判断当前实例所在的游戏客户端是否还有同客户端的其他实例。

        国服 / B服 / 国际服 是三个不同的游戏客户端, 各自保存独立的登录状态;
        国际服的所有区服(亚服、美服、欧服、港澳台服)共用同一个客户端。
        同客户端类型的实例多于一个时, 需要在切换实例时强制重新登录。
        """
        current_client = cls(current_idx).game_client
        client_count: dict[str, int] = {}
        for idx in instance_indices:
            client = cls(idx).game_client
            client_count[client] = client_count.get(client, 0) + 1
        return client_count.get(current_client, 0) > 1

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
    def bilibili_account_name(self) -> str:
        return self.get('bilibili_account_name', '')

    @bilibili_account_name.setter
    def bilibili_account_name(self, new_value: str) -> None:
        self.update('bilibili_account_name', new_value)

    @property
    def has_login_info(self) -> bool:
        if self.game_region == GameRegionEnum.CNB.value.value:
            return bool(self.bilibili_account_name.strip())
        return bool(self.account.strip() and self.password.strip())

    @property
    def game_client(self) -> str:
        """
        客户端类型: 国服 / B服 / 国际服 是三个不同的游戏客户端, 各自保存独立的登录状态。
        国际服的所有区服(亚服、美服、欧服、港澳台服)共用同一个客户端。
        """
        if self.game_region == GameRegionEnum.CN.value.value:
            return 'cn'
        elif self.game_region == GameRegionEnum.CNB.value.value:
            return 'cnb'
        return 'intl'

    @property
    def game_refresh_hour_offset(self) -> int:
        if self.game_region == GameRegionEnum.CN.value.value \
                or self.game_region == GameRegionEnum.CNB.value.value:
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
