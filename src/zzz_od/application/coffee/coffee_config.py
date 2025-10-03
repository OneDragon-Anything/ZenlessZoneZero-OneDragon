from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application.application_config import ApplicationConfig
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class CoffeeChooseWay(Enum):

    PLAN_PRIORITY = ConfigItem('优先体力计划', desc='优先选择符合体力计划的咖啡，没有的时候选择汀曼特调')
    CUSTOM = ConfigItem('汀曼特调', desc='只选择汀曼特调')


class CoffeeChallengeWay(Enum):

    ALL = ConfigItem('全都挑战')
    ONLY_PLAN = ConfigItem('只挑战体力计划')
    NONE = ConfigItem('不挑战')

class CoffeeCardNumEnum(Enum):
    # 注意需要跟charge_plan_config.CardNumEnum一致
    DEFAULT = ConfigItem('默认数量', desc='挑战体力计划外的副本时，按游戏内设数量')
    NUM_1 = ConfigItem('1', desc='挑战体力计划外的副本时，选择最少数量')


class CoffeeConfig(ApplicationConfig):

    def __init__(self, instance_idx: int, group_id: str):
        ApplicationConfig.__init__(
            self,
            instance_idx=instance_idx,
            app_id='coffee',
            group_id=group_id,
        )

    @property
    def choose_way(self) -> str:
        return self.get('choose_way', CoffeeChooseWay.PLAN_PRIORITY.value.value)

    @choose_way.setter
    def choose_way(self, new_value: str) -> None:
        self.update('choose_way', new_value)

    @property
    def challenge_way(self) -> str:
        return self.get('challenge_way', CoffeeChallengeWay.ALL.value.value)

    @challenge_way.setter
    def challenge_way(self, new_value: str) -> None:
        self.update('challenge_way', new_value)

    @property
    def card_num(self) -> str:
        return self.get('card_num', CoffeeCardNumEnum.NUM_1.value.value)

    @card_num.setter
    def card_num(self, new_value: str) -> None:
        self.update('card_num', new_value)

    @property
    def auto_battle(self) -> str:
        return self.get('auto_battle', '全配队通用')

    @auto_battle.setter
    def auto_battle(self, new_value: str) -> None:
        self.update('auto_battle', new_value)

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

    @property
    def predefined_team_idx(self) -> int:
        """
        预备编队 -1代表游戏内默认
        @return:
        """
        return self.get('predefined_team_idx', -1)

    @predefined_team_idx.setter
    def predefined_team_idx(self, new_value: int) -> None:
        self.update('predefined_team_idx', new_value)

    @property
    def run_charge_plan_afterwards(self) -> bool:
        """
        咖啡后 再次挑战体力计划
        @return:
        """
        return self.get('run_charge_plan_afterwards', False)

    @run_charge_plan_afterwards.setter
    def run_charge_plan_afterwards(self, new_value: bool) -> None:
        self.update('run_charge_plan_afterwards', new_value)
