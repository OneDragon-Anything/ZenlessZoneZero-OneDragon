import os
from typing import List, Optional

import yaml

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log


class CompendiumTab:

    def __init__(self, tab_name: str, category_list: List = None):
        self.tab_name: str = tab_name
        self.category_list: List[CompendiumCategory] = []
        if category_list is not None:
            for category_list_item in category_list:
                category_item = CompendiumCategory(**category_list_item)
                category_item.set_tab(self)
                self.category_list.append(category_item)


class CompendiumCategory:

    def __init__(self, category_name: str, mission_type_list: List = None):
        self.tab: Optional[CompendiumTab] = None
        self.category_name: str = category_name
        self.mission_type_list: List[CompendiumMissionType] = []
        if mission_type_list is not None:
            for mission_type_item in mission_type_list:
                mission_type = CompendiumMissionType(**mission_type_item)
                mission_type.set_category(self)
                self.mission_type_list.append(mission_type)

    def set_tab(self, tab: CompendiumTab):
        self.tab = tab


class CompendiumMissionType:

    def __init__(self, mission_type_name: str, mission_type_name_display: Optional[str] = None,
                 mission_list: List = None):
        self.category: Optional[CompendiumCategory] = None
        self.mission_type_name: str = mission_type_name
        self.mission_type_name_display: str = mission_type_name
        if mission_type_name_display is not None:
            self.mission_type_name_display = mission_type_name_display
        self.mission_list: List[CompendiumMission] = []
        if mission_list is not None:
            for mission_item in mission_list:
                mission = CompendiumMission(**mission_item)
                mission.set_mission_type(self)
                self.mission_list.append(mission)

    def set_category(self, category: CompendiumCategory):
        self.category = category


class CompendiumMission:

    def __init__(self, mission_name: str, mission_name_display: Optional[str] = None):
        self.mission_type: Optional[CompendiumMissionType] = None
        self.mission_name: str = mission_name
        self.mission_name_display: str = mission_name if mission_name_display is None else mission_name_display

    def set_mission_type(self, mission_type: CompendiumMissionType):
        self.mission_type = mission_type


class CompendiumData:

    def __init__(self, tab_list: List = None):
        self.tab_list: List[CompendiumTab] = []
        if tab_list is not None:
            for tab_item in tab_list:
                self.tab_list.append(CompendiumTab(**tab_item))


class Coffee:

    def __init__(self, coffee_name: str,
                 tab: Optional[CompendiumTab],
                 category: Optional[CompendiumCategory],
                 mission_type: Optional[CompendiumMissionType],
                 mission: Optional[CompendiumMission],
                 extra: bool = False):
        self.coffee_name: str = coffee_name
        self.tab: CompendiumTab = tab
        self.category: CompendiumCategory = category
        self.mission_type: CompendiumMissionType = mission_type
        self.mission: CompendiumMission = mission
        self.extra: bool = extra  # 可额外喝 不占用次数的

    @property
    def display_name(self) -> str:
        if self.mission_type is None:
            return self.coffee_name
        elif self.mission is None:
            return self.mission_type.mission_type_name_display
        else:
            return self.mission_type.mission_type_name_display + ' - ' + self.mission.mission_name_display

    @property
    def without_benefit(self) -> bool:
        """
        这种咖啡没有增益
        :return:
        """
        return self.mission_type is None


class CompendiumService:

    def __init__(self):
        self.data: CompendiumData = CompendiumData()
        self.coffee_list: List[Coffee] = []
        self.name_2_coffee: dict[str, Coffee] = {}
        self.coffee_schedule: dict[int, List[Coffee]] = {}

    def reload(self) -> None:
        """
        重新加载数据
        :return:
        """
        self._load_all_compendium()
        self._load_coffee()

    def _load_all_compendium(self) -> None:
        """
        加载副本
        :return:
        """
        file_path = os.path.join(
            os_utils.get_path_under_work_dir('assets', 'game_data'),
            'compendium_data.yml'
        )

        if not os.path.exists(file_path):
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                tab_list: List[dict] = yaml.safe_load(file)
                self.data = CompendiumData(tab_list)
        except Exception:
            log.error(f'文件读取失败 {file_path}', exc_info=True)

    def get_tab_data(self, tab_name: str) -> Optional[CompendiumTab]:
        for tab_item in self.data.tab_list:
            if tab_item.tab_name == tab_name:
                return tab_item
        return None

    def get_category_list_data(self, tab_name: str) -> List[CompendiumCategory]:
        tab = self.get_tab_data(tab_name)

        if tab is None:
            return []

        return tab.category_list

    def get_category_data(self, tab_name: str, category_name: str) -> Optional[CompendiumCategory]:
        category_list = self.get_category_list_data(tab_name)

        for category_item in category_list:
            if category_item.category_name == category_name:
                return category_item

        return None

    def get_mission_type_list_data(self, tab_name: str, category_name: str) -> List[CompendiumMissionType]:
        category: CompendiumCategory = self.get_category_data(tab_name, category_name)
        if category is not None:
            return category.mission_type_list
        else:
            return []

    def get_mission_type_data(self, tab_name: str, category_name: str, mission_type_name: str) -> Optional[CompendiumMissionType]:
        mission_type_list = self.get_mission_type_list_data(tab_name, category_name)

        for mission_type in mission_type_list:
            if mission_type.mission_type_name == mission_type_name:
                return mission_type

        return None

    def get_mission_list_data(self, tab_name: str, category_name: str, mission_type_name: str) -> List[CompendiumMission]:
        mission_type = self.get_mission_type_data(tab_name, category_name, mission_type_name)
        if mission_type is not None:
            return mission_type.mission_list
        else:
            return []

    def get_mission_data(self, tab_name: str, category_name: str, mission_type_name: str, mission_name: str) -> Optional[CompendiumMission]:
        mission_list = self.get_mission_list_data(tab_name, category_name, mission_type_name)
        for mission in mission_list:
            if mission.mission_name == mission_name:
                return mission

        return None

    def get_charge_plan_category_list(self) -> List[ConfigItem]:
        category_config_list: List[ConfigItem] = []

        category_list = self.get_category_list_data('训练')
        for category_item in category_list:
            category_config_list.append(ConfigItem(
                label=category_item.category_name,
                value=category_item.category_name
            ))

        category_list = self.get_category_list_data('作战')
        for category_item in category_list:
            if category_item.category_name == '恶名狩猎':
                category_config_list.append(ConfigItem(
                    label=f'{category_item.category_name} 深度追猎',
                    value=category_item.category_name
                ))

        return category_config_list

    def get_charge_plan_mission_type_list(self, category_name: str) -> List[ConfigItem]:
        config_list: List[ConfigItem] = []

        tab_name = '作战' if category_name == '恶名狩猎' else '训练'
        mission_type_list = self.get_mission_type_list_data(tab_name, category_name)
        for mission_type_item in mission_type_list:
            config_list.append(ConfigItem(
                label=mission_type_item.mission_type_name_display,
                value=mission_type_item.mission_type_name
            ))

        return config_list

    def get_charge_plan_mission_list(self, category_name: str, mission_type: str) -> List[ConfigItem]:
        config_list: List[ConfigItem] = []

        tab_name = '作战' if category_name == '恶名狩猎' else '训练'
        mission_list = self.get_mission_list_data(tab_name, category_name, mission_type)
        for mission_item in mission_list:
            config_list.append(ConfigItem(
                label=mission_item.mission_name_display,
                value=mission_item.mission_name
            ))

        return config_list

    def get_same_category_mission_type_list(self, mission_type_name: str) -> Optional[List[CompendiumMissionType]]:
        """
        获取与副本相同分类的全部列表
        """
        for tab in self.data.tab_list:
            for category in tab.category_list:
                for mission_type in category.mission_type_list:
                    if mission_type.mission_type_name == mission_type_name:
                        return category.mission_type_list

        return None

    def get_notorious_hunt_plan_mission_type_list(self, category_name: str) -> List[ConfigItem]:
        config_list: List[ConfigItem] = []

        mission_type_list = self.get_mission_type_list_data('作战', category_name)
        for mission_type_item in mission_type_list:
            config_list.append(ConfigItem(
                label=mission_type_item.mission_type_name_display,
                value=mission_type_item.mission_type_name
            ))

        return config_list

    def get_hollow_zero_mission_name_list(self) -> List[str]:
        mission_name_list: List[str] = []
        mission_type_list = self.get_mission_type_list_data('作战', '零号空洞')
        for mission_type in mission_type_list:
            for mission in mission_type.mission_list:
                mission_name_list.append(mission.mission_name)
        return mission_name_list

    def _load_coffee(self) -> None:
        """
        加载咖啡相关数据
        :return:
        """
        file_path = os.path.join(
            os_utils.get_path_under_work_dir('assets', 'game_data'),
            'coffee_data.yml'
        )

        if not os.path.exists(file_path):
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                self.coffee_list = []
                self.name_2_coffee = {}

                for i in data.get('coffee_list', []):
                    coffee = self._construct_coffee(**i)
                    self.coffee_list.append(coffee)
                    self.name_2_coffee[coffee.coffee_name] = coffee

                self.coffee_schedule = {}
                for schedule in data.get('schedule', []):
                    coffee_list = [self.name_2_coffee[coffee_name] for coffee_name in schedule.get('coffee_list', [])]
                    for day in schedule.get('days', []):
                        self.coffee_schedule[day] = coffee_list


        except Exception:
            log.error(f'文件读取失败 {file_path}', exc_info=True)

    def _construct_coffee(self, coffee_name: str,
                          tab_name: Optional[str] = None,
                          category_name: Optional[str] = None,
                          mission_type_name: Optional[str] = None,
                          mission_name: Optional[str] = None,
                          extra: bool = False
                          ) -> Coffee:
        tab = self.get_tab_data(tab_name)
        category = self.get_category_data(tab_name, category_name)
        mission_type = self.get_mission_type_data(tab_name, category_name, mission_type_name)
        mission = self.get_mission_data(tab_name, category_name, mission_type_name, mission_name)

        return Coffee(coffee_name, tab, category, mission_type, mission, extra=extra)

    def get_coffee_config_list_by_day(self, day: int) -> List[ConfigItem]:
        return [ConfigItem(i.display_name, i.coffee_name) for i in self.coffee_schedule.get(day, [])]

    def get_extra_coffee_list(self) -> List[Coffee]:
        return [i for i in self.coffee_list if i.extra]

    def get_lost_void_mission_name_list(self) -> List[str]:
        """
        迷失之地的关卡名称列表
        :return:
        """
        mission_name_list: List[str] = []
        mission_list = self.get_mission_list_data('作战', '零号空洞', '迷失之地')
        for mission in mission_list:
            mission_name_list.append(mission.mission_name_display)
        return mission_name_list