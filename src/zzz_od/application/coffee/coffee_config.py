from enum import Enum

from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.game_data.map_area import TransportPoint


class CoffeeTransportPoint(Enum):

    POINT_1 = TransportPoint('六分街', '咖啡店')
    POINT_2 = TransportPoint('澄辉坪', '汀曼咖啡')
    POINT_3 = TransportPoint('布亚斯特城区', '片刻闲')


class CoffeeConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            instance_idx=instance_idx,
            app_id='coffee',
            group_id=group_id,
        )

    @property
    def transport_point(self) -> str:
        return self.get('transport_point', CoffeeTransportPoint.POINT_1.value.value)

    @transport_point.setter
    def transport_point(self, new_value: str) -> None:
        self.update('transport_point', new_value)

    @property
    def run_charge_plan_afterwards(self) -> bool:
        """咖啡后运行体力计划"""
        return self.get('run_charge_plan_afterwards', False)

    @run_charge_plan_afterwards.setter
    def run_charge_plan_afterwards(self, new_value: bool) -> None:
        self.update('run_charge_plan_afterwards', new_value)
