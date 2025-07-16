from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig

class ThemeEnum(Enum):

    LIGHT = ConfigItem('浅色', 'Light')
    DARK = ConfigItem('深色', 'Dark')
    AUTO = ConfigItem('跟随系统', 'Auto')

class CustomConfig(YamlConfig):

    def __init__(self):
        super().__init__(module_name='custom')
    

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
    def banner(self) -> bool:
        """
        自定义主页背景
        :return:
        """
        return self.get('banner', False)
    
    @banner.setter
    def banner(self, new_value: bool) -> None:
        """
        自定义主页背景
        :return:
        """
        self.update('banner', new_value)