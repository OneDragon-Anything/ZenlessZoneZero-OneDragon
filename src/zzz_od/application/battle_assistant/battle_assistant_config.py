from one_dragon.base.config.yaml_config import YamlConfig
from zzz_od.config.game_config import GamepadTypeEnum


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
    def use_gpu(self) -> bool:
        return self.get('use_gpu', True)

    @use_gpu.setter
    def use_gpu(self, new_value: bool) -> None:
        self.update('use_gpu', new_value)

    @property
    def screenshot_interval(self) -> float:
        return self.get('screenshot_interval', 0.02)

    @screenshot_interval.setter
    def screenshot_interval(self, new_value: float) -> None:
        self.update('screenshot_interval', new_value)

    @property
    def gamepad_type(self) -> str:
        return self.get('gamepad_type', GamepadTypeEnum.NONE.value.value)

    @gamepad_type.setter
    def gamepad_type(self, new_value: str) -> None:
        self.update('gamepad_type', new_value)

    @property
    def auto_battle_config(self) -> str:
        return self.get('auto_battle_config', '全配队通用')

    @auto_battle_config.setter
    def auto_battle_config(self, new_value: str) -> None:
        self.update('auto_battle_config', new_value)

    @property
    def debug_operation_config(self) -> str:
        return self.get('debug_operation_config', '安比-3A特殊攻击')

    @debug_operation_config.setter
    def debug_operation_config(self, new_value: str) -> None:
        self.update('debug_operation_config', new_value)

    @property
    def debug_operation_repeat(self) -> bool:
        return self.get('debug_operation_repeat', True)

    @debug_operation_repeat.setter
    def debug_operation_repeat(self, new_value: bool) -> None:
        self.update('debug_operation_repeat', new_value)

    @property
    def use_merged_file(self) -> bool:
        """使用合并后的单文件"""
        return self.get('use_merged_file', True)

    @use_merged_file.setter
    def use_merged_file(self, new_value: bool) -> None:
        self.update('use_merged_file', new_value)
