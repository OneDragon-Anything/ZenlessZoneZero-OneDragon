from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application.application_config import ApplicationConfig
from zzz_od.game_data.map_area import TransportPoint


class CoffeeTransportPoint(Enum):

    POINT_1 = TransportPoint('六分街', '咖啡店')
    POINT_2 = TransportPoint('澄辉坪', '汀曼咖啡')


class CoffeeChooseWay(Enum):

    PLAN_PRIORITY = ConfigItem('优先双倍活动', desc='喝后挑战沿用体力计划且双倍活动开启时选择浓缩咖啡等，否则选择汀曼特调')
    TINMAN_ONLY = ConfigItem('汀曼特调', desc='只选择汀曼特调')
    ESPRESSO_ONLY = ConfigItem('浓缩咖啡', desc='只选择浓缩咖啡')


class CoffeeChallengeWay(Enum):

    DEFAULT = ConfigItem('沿用体力计划', desc='喝完咖啡后运行体力计划，优先处理已开启的双倍活动')
    NO_DOUBLE = ConfigItem('沿用体力计划（不考虑双倍活动）', desc='喝完咖啡后运行体力计划，本次跳过双倍活动')
    NONE = ConfigItem('不挑战', desc='只喝咖啡，不自动进入副本')


class CoffeeConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            instance_idx=instance_idx,
            app_id='coffee',
            group_id=group_id,
        )

        # 旧配置清理，2026-10-12 可删除
        self._clear_legacy_config()

    def _clear_legacy_config(self) -> None:
        changed = False
        if self.get('challenge_way', None) in ['全都挑战', '只挑战体力计划']:
            self.data.pop('challenge_way')
            changed = True
        if self.get('choose_way', None) == '优先体力计划':
            self.data.pop('choose_way')
            changed = True
        for key in ['card_num', 'predefined_team_idx', 'auto_battle', 'run_charge_plan_afterwards']:
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

    @property
    def challenge_way(self) -> str:
        return self.get('challenge_way', CoffeeChallengeWay.DEFAULT.value.value)

    @challenge_way.setter
    def challenge_way(self, new_value: str) -> None:
        self.update('challenge_way', new_value)

    @property
    def day_coffee_1(self) -> str:
        return self.get('day_coffee_1', '汀曼特调')

    @day_coffee_1.setter
    def day_coffee_1(self, new_value: str) -> None:
        self.update('day_coffee_1', new_value)

    @property
    def day_coffee_2(self) -> str:
        return self.get('day_coffee_2', '汀曼特调')

    @day_coffee_2.setter
    def day_coffee_2(self, new_value: str) -> None:
        self.update('day_coffee_2', new_value)

    @property
    def day_coffee_3(self) -> str:
        return self.get('day_coffee_3', '汀曼特调')

    @day_coffee_3.setter
    def day_coffee_3(self, new_value: str) -> None:
        self.update('day_coffee_3', new_value)

    @property
    def day_coffee_4(self) -> str:
        return self.get('day_coffee_4', '汀曼特调')

    @day_coffee_4.setter
    def day_coffee_4(self, new_value: str) -> None:
        self.update('day_coffee_4', new_value)

    @property
    def day_coffee_5(self) -> str:
        return self.get('day_coffee_5', '汀曼特调')

    @day_coffee_5.setter
    def day_coffee_5(self, new_value: str) -> None:
        self.update('day_coffee_5', new_value)

    @property
    def day_coffee_6(self) -> str:
        return self.get('day_coffee_6', '汀曼特调')

    @day_coffee_6.setter
    def day_coffee_6(self, new_value: str) -> None:
        self.update('day_coffee_6', new_value)

    @property
    def day_coffee_7(self) -> str:
        return self.get('day_coffee_7', '汀曼特调')

    @day_coffee_7.setter
    def day_coffee_7(self, new_value: str) -> None:
        self.update('day_coffee_7', new_value)

    def get_coffee_by_day(self, day: int) -> str:
        """
        根据星期几获取对应的咖啡名称
        :param day: 1~7
        :return:
        """
        if day == 1:
            return self.day_coffee_1
        elif day == 2:
            return self.day_coffee_2
        elif day == 3:
            return self.day_coffee_3
        elif day == 4:
            return self.day_coffee_4
        elif day == 5:
            return self.day_coffee_5
        elif day == 6:
            return self.day_coffee_6
        elif day == 7:
            return self.day_coffee_7
