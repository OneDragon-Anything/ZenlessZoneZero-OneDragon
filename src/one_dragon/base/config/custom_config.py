from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig


class UILanguageEnum(Enum):

    AUTO = ConfigItem('跟随系统', 'auto')
    ZH = ConfigItem('简体中文', 'zh')
    EN = ConfigItem('English', 'en')

class ThemeEnum(Enum):

    AUTO = ConfigItem('跟随系统', 'Auto')
    LIGHT = ConfigItem('浅色', 'Light')
    DARK = ConfigItem('深色', 'Dark')

class CustomConfig(YamlConfig):

    def __init__(self):
        super().__init__(module_name='custom')

    @property
    def ui_language(self) -> str:
        """
        界面语言
        :return:
        """
        return self.get('ui_language', UILanguageEnum.AUTO.value.value)

    @ui_language.setter
    def ui_language(self, new_value: str) -> None:
        """
        界面语言
        :return:
        """
        self.update('ui_language', new_value)

    @property
    def theme(self) -> str:
        """
        主题
        :return:
        """
        return self.get('theme', ThemeEnum.AUTO.value.value)

    @theme.setter
    def theme(self, new_value: str) -> None:
        """
        主题
        :return:
        """
        self.update('theme', new_value)

    @property
    def notice_card(self) -> bool:
        """
        是否启用公告
        :return:
        """
        return self.get('notice_card', True)

    @notice_card.setter
    def notice_card(self, new_value: bool) -> None:
        """
        是否启用公告
        :return:
        """
        self.update('notice_card', new_value)

    @property
    def custom_banner(self) -> bool:
        """
        自定义主页背景
        :return:
        """
        return self.get('custom_banner', False)

    @custom_banner.setter
    def custom_banner(self, new_value: bool) -> None:
        """
        自定义主页背景
        :return:
        """
        self.update('custom_banner', new_value)

    @property
    def remote_banner(self) -> bool:
        """
        是否启用远端主页背景
        """
        return self.get('remote_banner', True)

    @remote_banner.setter
    def remote_banner(self, new_value: bool) -> None:
        self.update('remote_banner', new_value)

    @property
    def version_poster(self) -> bool:
        """
        是否启用版本海报
        """
        return self.get('version_poster', False)

    @version_poster.setter
    def version_poster(self, new_value: bool) -> None:
        self.update('version_poster', new_value)

    @property
    def last_remote_banner_fetch_time(self) -> str:
        """
        上次获取远端主页背景的时间
        """
        return self.get('last_remote_banner_fetch_time', '')

    @last_remote_banner_fetch_time.setter
    def last_remote_banner_fetch_time(self, new_value: str) -> None:
        self.update('last_remote_banner_fetch_time', new_value)

    @property
    def last_version_poster_fetch_time(self) -> str:
        """
        上次获取版本海报的时间
        """
        return self.get('last_version_poster_fetch_time', '')

    @last_version_poster_fetch_time.setter
    def last_version_poster_fetch_time(self, new_value: str) -> None:
        self.update('last_version_poster_fetch_time', new_value)
