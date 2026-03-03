from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application.application_config import ApplicationConfig


class OutpostLogisticsObtainNumber(Enum):

    ALL = ConfigItem('全部', 10)
    ONE = ConfigItem('1个', 1)
    TWO = ConfigItem('2个', 2)
    THREE = ConfigItem('3个', 3)
    FOUR = ConfigItem('4个', 4)
    FIVE = ConfigItem('5个', 5)
    SIX = ConfigItem('6个', 6)
    SEVEN = ConfigItem('7个', 7)
    EIGHT = ConfigItem('8个', 8)
    NINE = ConfigItem('9个', 9)


class MonthlyRestockObtainNumber(Enum):

    ALL = ConfigItem('全部', 5)
    ONE = ConfigItem('1个', 1)
    TWO = ConfigItem('2个', 2)
    THREE = ConfigItem('3个', 3)
    FOUR = ConfigItem('4个', 4)


class FadingSignalObtainNumber(Enum):

    ALL = ConfigItem('全部', 20)
    ONE = ConfigItem('1个', 1)
    TWO = ConfigItem('2个', 2)
    THREE = ConfigItem('3个', 3)
    FOUR = ConfigItem('4个', 4)
    FIVE = ConfigItem('5个', 5)
    SIX = ConfigItem('6个', 6)
    SEVEN = ConfigItem('7个', 7)
    EIGHT = ConfigItem('8个', 8)
    NINE = ConfigItem('9个', 9)
    TEN = ConfigItem('10个', 10)
    ELEVEN = ConfigItem('11个', 11)
    TWELVE = ConfigItem('12个', 12)
    THIRTEEN = ConfigItem('13个', 13)
    FOURTEEN = ConfigItem('14个', 14)
    FIFTEEN = ConfigItem('15个', 15)
    SIXTEEN = ConfigItem('16个', 16)
    SEVENTEEN = ConfigItem('17个', 17)
    EIGHTEEN = ConfigItem('18个', 18)
    NINETEEN = ConfigItem('19个', 19)


class UseTheme(Enum):

    DEFAULT = ConfigItem('常规主题')
    NEON_RUINS = ConfigItem('霓虹遗迹')
    PURSUIT_OF_FUN = ConfigItem('玩乐主义')
    RANDOM_PLAY = ConfigItem('Random Play')
    SAN_Z = ConfigItem('三Z')
    SWEETYS_DRUNK_ON_THE_SPRING_BREEZE = ConfigItem('红豆醉春风')
    SWEET_DAYDREAM = ConfigItem('甜味白日梦')


class AutoObtainPrepaidPowerCardConfig(ApplicationConfig):
    def __init__(self, instance_idx: int, group_id: str) -> None:
        ApplicationConfig.__init__(
            self,
            instance_idx=instance_idx,
            app_id='auto_obtain_prepaid_power_card',
            group_id=group_id,
        )

    @property
    def outpost_logistics(self) -> bool:
        return self.get('outpost_logistics', False)

    @outpost_logistics.setter
    def outpost_logistics(self, value: bool) -> None:
        self.update('outpost_logistics', value)

    @property
    def monthly_restock(self) -> bool:
        return self.get('monthly_restock', False)

    @monthly_restock.setter
    def monthly_restock(self, value: bool) -> None:
        self.update('monthly_restock', value)

    @property
    def fading_signal(self) -> bool:
        return self.get('fading_signal', False)

    @fading_signal.setter
    def fading_signal(self, value: bool) -> None:
        self.update('fading_signal', value)

    @property
    def outpost_logistics_obtain_number(self) -> int:
        return self.get('outpost_logistics_obtain_number', OutpostLogisticsObtainNumber.ALL.value.value)

    @outpost_logistics_obtain_number.setter
    def outpost_logistics_obtain_number(self, value: int) -> None:
        self.update('outpost_logistics_obtain_number', value)

    @property
    def monthly_restock_obtain_number(self) -> int:
        return self.get("monthly_restock_obtain_number", MonthlyRestockObtainNumber.ALL.value.value)

    @monthly_restock_obtain_number.setter
    def monthly_restock_obtain_number(self, value: int) -> None:
        self.update('monthly_restock_obtain_number', value)

    @property
    def fading_signal_obtain_number(self) -> int:
        return self.get("fading_signal_obtain_number", FadingSignalObtainNumber.ALL.value.value)

    @fading_signal_obtain_number.setter
    def fading_signal_obtain_number(self, value: int) -> None:
        self.update('fading_signal_obtain_number', value)
