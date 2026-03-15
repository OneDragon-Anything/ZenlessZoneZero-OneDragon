from enum import Enum
from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application.application_config import ApplicationConfig


class SourceEtherBatteryAutoSyntheticQuantity(Enum):
    ALL = ConfigItem('全部', value='ALL')
    ONE = ConfigItem('一个', value='ONE')
    TWO = ConfigItem('两个', value='TWO')
    THREE = ConfigItem('三个', value='THREE')
    FOUR = ConfigItem('四个', value='FOUR')

    def get_click_count(self, max_available: int) -> int:
        """获取需要点击的次数"""
        click_map = {
            'ALL': max_available,
            'FOUR': min(3, max_available),
            'THREE': min(2, max_available),
            'TWO': min(1, max_available),
            'ONE': 0,
        }
        return click_map.get(self.value.value, 0)


class AutoSyntheticConfig(ApplicationConfig):
    def __init__(self, instance_idx: int, group_id: str) -> None:
        ApplicationConfig.__init__(self, 'auto_synthetic', instance_idx, group_id)

    @property
    def hifi_master_copy(self) -> bool:
        return self.get('hifi_master_copy', True)

    @hifi_master_copy.setter
    def hifi_master_copy(self, value: bool) -> None:
        self.update('hifi_master_copy', value)

    @property
    def source_ether_battery(self) -> bool:
        return self.get('source_ether_battery', False)

    @source_ether_battery.setter
    def source_ether_battery(self, value: bool) -> None:
        self.update('source_ether_battery', value)

    @property
    def source_ether_battery_auto_synthetic_quantity(self) -> str:
        return self.get(
            'source_ether_battery_auto_synthetic_quantity',
            SourceEtherBatteryAutoSyntheticQuantity.ALL.value
        )

    @source_ether_battery_auto_synthetic_quantity.setter
    def source_ether_battery_auto_synthetic_quantity(self, value: str) -> None:
        self.update('source_ether_battery_auto_synthetic_quantity', value)

    def get_battery_click_count(self, max_available: int) -> int:
        """获取电池合成需要点击的次数"""
        try:
            quantity = SourceEtherBatteryAutoSyntheticQuantity(
                self.source_ether_battery_auto_synthetic_quantity
            )
            return quantity.get_click_count(max_available - 1)
        except ValueError:
            return 0