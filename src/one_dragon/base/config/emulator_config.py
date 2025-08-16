from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.base.config.json_config import JsonConfig
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter
from one_dragon_qt.widgets.setting_card.json_config_adapter import JsonConfigAdapter

class GameClient(Enum):
    android_game = ConfigItem('安卓端', 'android')
    cloud_game = ConfigItem('云游戏安卓端', 'cloud_android')


class EmulatorConfig(JsonConfig):
    def __init__(self, instance_idx: int):
        JsonConfig.__init__(self, 'alas', instance_idx=instance_idx)



    @property
    def Alas_Emulator_Serial_adapter(self) -> JsonConfigAdapter:
        return JsonConfigAdapter(self, 'Alas.Emulator.Serial')

    @property
    def Alas_Emulator_GameClient_adapter(self) -> JsonConfigAdapter:
        return JsonConfigAdapter(self, 'Alas.Emulator.GameClient')
    
    @property
    def Alas_EmulatorInfo_path_adapter(self) -> JsonConfigAdapter:
        return JsonConfigAdapter(self, 'Alas.EmulatorInfo.path')
        # 这个用不了 用的下面的方法

    @property
    def emulator_path(self) -> str:
        return self.data['Alas']['EmulatorInfo'].get('path', '')

    @emulator_path.setter
    def emulator_path(self, new_value: str) -> None:
        self.data['Alas']['EmulatorInfo']['path'] = new_value
        self.save()



