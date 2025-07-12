from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig


class AgentOutfitConfig(YamlConfig):

    def __init__(self, instance_idx: int):
        YamlConfig.__init__(self, 'agent_outfit', instance_idx=instance_idx)

    @property
    def compatibility_mode(self) -> bool:
        return self.get('compatibility_mode', False)

    @compatibility_mode.setter
    def compatibility_mode(self, value: bool) -> None:
        self.update('compatibility_mode', value)

    @property
    def nicole_outfit_list(self) -> str:
        return self.get('nicole_outfit_list', [AgentOutfitNicole.DEFAULT.value.value,
                                               AgentOutfitNicole.CUNNING_CUTIE.value.value])

    @property
    def nicole(self) -> str:
        return self.get('nicole', AgentOutfitNicole.DEFAULT.value.value)

    @nicole.setter
    def nicole(self, value: str) -> None:
        self.update('nicole', value)

    @property
    def ellen_outfit_list(self) -> str:
        return self.get('ellen_outfit_list', [AgentOutfitEllen.DEFAULT.value.value,
                                              AgentOutfitEllen.ON_CAMPUS.value.value])

    @property
    def ellen(self) -> str:
        return self.get('ellen', AgentOutfitEllen.DEFAULT.value.value)

    @ellen.setter
    def ellen(self, value: str) -> None:
        self.update('ellen', value)

    @property
    def astra_yao_outfit_list(self) -> str:
        return self.get('astra_yao_outfit_list', [AgentOutfitAstraYao.DEFAULT.value.value,
                                                  AgentOutfitAstraYao.CHANDELIER.value.value])

    @property
    def astra_yao(self) -> str:
        return self.get('astra_yao', AgentOutfitAstraYao.DEFAULT.value.value)

    @astra_yao.setter
    def astra_yao(self, value: str) -> None:
        self.update('astra_yao', value)

    @property
    def yixuan_outfit_list(self) -> str:
        return self.get('yixuan_outfit_list', [AgentOutfitYiXuan.DEFAULT.value.value,
                                               AgentOutfitYiXuan.TRAILS_OF_INK.value.value])

    @property
    def yixuan(self) -> str:
        return self.get('yixuan', AgentOutfitYiXuan.DEFAULT.value.value)

    @yixuan.setter
    def yixuan(self, value: str) -> None:
        self.update('yixuan', value)

class AgentOutfitNicole(Enum):
    """
    妮可皮肤
    """
    DEFAULT = ConfigItem('默认', 'nicole')
    CUNNING_CUTIE = ConfigItem('狡黠甜心', 'nicole_cunning_cutie')


class AgentOutfitEllen(Enum):
    """
    艾莲皮肤
    """
    DEFAULT = ConfigItem('默认', 'ellen')
    ON_CAMPUS = ConfigItem('从周一到周五', 'ellen_on_campus')


class AgentOutfitAstraYao(Enum):
    """
    耀嘉音皮肤
    """
    DEFAULT = ConfigItem('默认', 'astra_yao')
    CHANDELIER = ConfigItem('水晶灯下', 'astra_yao_chandelier')

class AgentOutfitYiXuan(Enum):
    """
    仪玄皮肤
    """
    DEFAULT = ConfigItem('默认', 'yixuan')
    TRAILS_OF_INK = ConfigItem('墨形影踪', 'yixuan_trails_of_ink')