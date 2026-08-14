from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.game_data.map_area import TransportPoint


class CoffeeTransportPoint(Enum):

    POINT_1 = TransportPoint('六分街', '咖啡店')
    POINT_2 = TransportPoint('澄辉坪', '汀曼咖啡')
    POINT_3 = TransportPoint('布亚斯特城区', '片刻闲')


class CoffeeChooseWay(Enum):

    TINMAN_ONLY = ConfigItem('汀曼特调', desc='固定选择汀曼特调')


class CoffeeConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            instance_idx=instance_idx,
            app_id='coffee',
            group_id=group_id,
        )

        self._migrate_legacy_config()

    def _migrate_legacy_config(self) -> None:
        changed = False
        if self.get('choose_way', None) != CoffeeChooseWay.TINMAN_ONLY.value.value:
            self.data['choose_way'] = CoffeeChooseWay.TINMAN_ONLY.value.value
            changed = True

        for key in (
            'challenge_way',
            'card_num',
            'auto_battle',
            'predefined_team_idx',
            'day_coffee_1',
            'day_coffee_2',
            'day_coffee_3',
            'day_coffee_4',
            'day_coffee_5',
            'day_coffee_6',
            'day_coffee_7',
        ):
            if key in self.data:
                self.data.pop(key)
                changed = True

        if changed:
            self.save()

    @property
    def transport_point(self) -> str:
        return self.get('transport_point', CoffeeTransportPoint.POINT_1.value.value)

    @transport_point.setter
    def transport_point(self, new_value: str) -> None:
        self.update('transport_point', new_value)

    @property
    def choose_way(self) -> str:
        return self.get('choose_way', CoffeeChooseWay.TINMAN_ONLY.value.value)

    @choose_way.setter
    def choose_way(self, new_value: str) -> None:
        self.update('choose_way', new_value)

    def get_coffee_by_day(self, _day: int) -> str:
        """所有星期固定返回汀曼特调"""
        return CoffeeChooseWay.TINMAN_ONLY.value.value

    @property
    def run_charge_plan_afterwards(self) -> bool:
        """咖啡后运行体力计划"""
        return self.get('run_charge_plan_afterwards', False)

    @run_charge_plan_afterwards.setter
    def run_charge_plan_afterwards(self, new_value: bool) -> None:
        self.update('run_charge_plan_afterwards', new_value)
