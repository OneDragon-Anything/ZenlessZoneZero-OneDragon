from one_dragon.base.config.yaml_config import YamlConfig
from zzz_od.config.game_config import ControlMethodEnum


class BattleAssistantConfig(YamlConfig):

    def __init__(self, instance_idx: int):
        YamlConfig.__init__(self, 'battle_assistant', instance_idx=instance_idx)

    @property
    def dodge_assistant_config(self) -> str:
        return self.get('dodge_assistant_config', '闪避')

    @dodge_assistant_config.setter
    def dodge_assistant_config(self, new_value: str) -> None:
        self.update('dodge_assistant_config', new_value)

    @property
    def screenshot_interval(self) -> float:
        return self.get('screenshot_interval', 0.02)

    @screenshot_interval.setter
    def screenshot_interval(self, new_value: float) -> None:
        self.update('screenshot_interval', new_value)

    @property
    def control_method(self) -> str:
        return self.get('control_method', ControlMethodEnum.KEYBOARD.value.value)

    @control_method.setter
    def control_method(self, new_value: str) -> None:
        self.update('control_method', new_value)

    @property
    def auto_battle_config(self) -> str:
        return self.get('auto_battle_config', '全配队通用')

    @auto_battle_config.setter
    def auto_battle_config(self, new_value: str) -> None:
        self.update('auto_battle_config', new_value)

    @property
    def use_merged_file(self) -> bool:
        """使用合并后的单文件"""
        return self.get('use_merged_file', True)

    @use_merged_file.setter
    def use_merged_file(self, new_value: bool) -> None:
        self.update('use_merged_file', new_value)

    @property
    def auto_ultimate_enabled(self) -> bool:
        """自动释放终结技开关"""
        return self.get('auto_ultimate_enabled', False)

    @auto_ultimate_enabled.setter
    def auto_ultimate_enabled(self, new_value: bool) -> None:
        self.update('auto_ultimate_enabled', new_value)
