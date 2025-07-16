from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class TypeInputWay(Enum):
    INPUT = ConfigItem('键盘输入', 'input', desc='需确保使用时没有启用输入法')
    CLIPBOARD = ConfigItem('剪贴板', 'clipboard', desc='出现剪切板失败时 切换到输入法')


class ScreenSizeEnum(Enum):
    SIZE_1920_1080 = ConfigItem('1920x1080', '1920x1080')
    SIZE_2560_1440 = ConfigItem('2560x1440', '2560x1440')
    SIZE_3840_2160 = ConfigItem('3840x2160', '3840x2160')


class FullScreenEnum(Enum):
    WINDOWED = ConfigItem('窗口化', '0')
    FULL_SCREEN = ConfigItem('全屏', '1')


class MonitorEnum(Enum):
    MONITOR_1 = ConfigItem('1', '1')
    MONITOR_2 = ConfigItem('2', '2')
    MONITOR_3 = ConfigItem('3', '3')
    MONITOR_4 = ConfigItem('4', '4')


class BasicGameConfig(YamlConfig):

    def __init__(self, instance_idx: int):
        YamlConfig.__init__(self, 'game', instance_idx=instance_idx)

    @property
    def type_input_way(self) -> str:
        return self.get('type_input_way', TypeInputWay.CLIPBOARD.value.value)

    @type_input_way.setter
    def type_input_way(self, new_value: str):
        self.update('type_input_way', new_value)

    @property
    def type_input_way_adapter(self) -> YamlConfigAdapter:
        return YamlConfigAdapter(self, 'type_input_way', TypeInputWay.CLIPBOARD.value.value)

    @property
    def hdr(self) -> bool:
        return self.get('hdr', False)
    
    @hdr.setter
    def hdr(self, new_value: bool) -> None:
        self.update('hdr', new_value)

    @property
    def launch_argument(self) -> bool:
        return self.get('launch_argument', False)

    @launch_argument.setter
    def launch_argument(self, new_value: bool) -> None:
        self.update('launch_argument', new_value)

    @property
    def screen_size(self) -> str:
        return self.get('screen_size', ScreenSizeEnum.SIZE_1920_1080.value.value)

    @screen_size.setter
    def screen_size(self, new_value: str) -> None:
        self.update('screen_size', new_value)

    @property
    def full_screen(self) -> str:
        return self.get('full_screen', FullScreenEnum.WINDOWED.value.value)

    @full_screen.setter
    def full_screen(self, new_value: str) -> None:
        self.update('full_screen', new_value)

    @property
    def popup_window(self) -> bool:
        return self.get('popup_window', False)

    @popup_window.setter
    def popup_window(self, new_value: bool) -> None:
        self.update('popup_window', new_value)

    @property
    def monitor(self) -> str:
        return self.get('monitor', MonitorEnum.MONITOR_1.value.value)

    @monitor.setter
    def monitor(self, new_value: str) -> None:
        self.update('monitor', new_value)

    @property
    def launch_argument_advance(self) -> str:
        return self.get('launch_argument_advance', '')

    @launch_argument_advance.setter
    def launch_argument_advance(self, new_value: str) -> None:
        self.update('launch_argument_advance', new_value)