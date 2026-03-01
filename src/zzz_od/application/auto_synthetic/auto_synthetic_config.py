from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application.application_config import ApplicationConfig


class SourceEtherBatteryAutoSyntheticQuantity(Enum):

    ALL = ConfigItem('全部')
    ONE = ConfigItem('一个')
    TWO = ConfigItem('两个')
    THREE = ConfigItem('三个')
    FOUR = ConfigItem('四个')

class AutoSyntheticConfig(ApplicationConfig):
    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(self, 'auto_synthetic', instance_idx, group_id)

    @property
    def hifi_master_copy(self) -> bool:
        return self.get('hifi_master_copy', True)

    @hifi_master_copy.setter
    def hifi_master_copy(self, value) -> None:
        self.update('hifi_master_copy', value)

    @property
    def source_ether_battery(self) -> bool:
        return self.get('source_ether_battery', False)

    @source_ether_battery.setter
    def source_ether_battery(self, value) -> None:
        self.update('source_ether_battery', value)

    @property
    def source_ether_battery_auto_synthetic_quantity(self) -> str:
        return self.get('source_ether_battery_auto_synthetic_quantity', SourceEtherBatteryAutoSyntheticQuantity.ALL.value.value)

    @source_ether_battery_auto_synthetic_quantity.setter
    def source_ether_battery_auto_synthetic_quantity(self, value) -> None:
        self.update('source_ether_battery_auto_synthetic_quantity', value)