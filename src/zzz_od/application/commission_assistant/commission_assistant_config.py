from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.application.devtools.screenshot_helper import screenshot_helper_const


class DialogOptionEnum(Enum):

    FIRST = ConfigItem('第一个')
    LAST = ConfigItem('最后一个')


class StoryMode(Enum):

    CLICK = ConfigItem('自动点击')
    AUTO = ConfigItem('等待剧情自动播放')
    SKIP = ConfigItem('跳过剧情')


class CommissionAssistantConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            app_id=screenshot_helper_const.APP_ID,
            instance_idx=instance_idx,
            group_id=group_id,
        )
        self.OPTION_CLICK_INTERVAL_MIN = 0.1  # 选项的最小点击间隔(需要等待点击动画结束0.2s, 减去pyautogui.click()自带的0.1s)

    @property
    def dialog_click_interval(self) -> float:
        return self.get('dialog_click_interval', 0.5)

    @dialog_click_interval.setter
    def dialog_click_interval(self, new_value: float) -> None:
        self.update('dialog_click_interval', new_value)

    @property
    def story_mode(self):
        return self.get('story_mode', StoryMode.CLICK.value.value)

    @story_mode.setter
    def story_mode(self, new_value: str) -> None:
        self.update('story_mode', new_value)

    @property
    def dialog_option(self) -> str:
        return self.get('dialog_option', DialogOptionEnum.LAST.value.value)

    @dialog_option.setter
    def dialog_option(self, new_value: str) -> None:
        self.update('dialog_option', new_value)

    @property
    def dodge_config(self) -> str:
        return self.get('dodge_config', '闪避')

    @dodge_config.setter
    def dodge_config(self, new_value: str) -> None:
        self.update('dodge_config', new_value)

    @property
    def dodge_switch(self) -> str:
        return self.get('dodge_switch', '5')

    @dodge_switch.setter
    def dodge_switch(self, new_value: str) -> None:
        self.update('dodge_switch', new_value)

    @property
    def auto_battle(self) -> str:
        return self.get('auto_battle', '全配队通用')

    @auto_battle.setter
    def auto_battle(self, new_value: str) -> None:
        self.update('auto_battle', new_value)

    @property
    def auto_battle_switch(self) -> str:
        return self.get('auto_battle_switch', '6')

    @auto_battle_switch.setter
    def auto_battle_switch(self, new_value: str) -> None:
        self.update('auto_battle_switch', new_value)

    @property
    def sleep_after_empty_screen(self) -> float:
        return self.get('sleep_after_empty_screen', 0.5)

    @sleep_after_empty_screen.setter
    def sleep_after_empty_screen(self, new_value: float) -> None:
        self.update('sleep_after_empty_screen', new_value)