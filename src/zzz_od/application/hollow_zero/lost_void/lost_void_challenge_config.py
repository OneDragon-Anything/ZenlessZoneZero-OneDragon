import os
from enum import Enum
from typing import List

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log


class LostVoidRegionType(Enum):
    """
    注意需要和识别模型的结果名称一致
    """

    ENTRY = ConfigItem('入口')
    COMBAT_RESONIUM = ConfigItem('战斗-鸣徽')
    COMBAT_GEAR = ConfigItem('战斗-武备')
    COMBAT_COIN = ConfigItem('战斗-硬币')
    CHANLLENGE_FLAWLESS = ConfigItem('挑战-无伤')
    CHANLLENGE_TIME_TRAIL = ConfigItem('挑战-限时')
    CHANLLENGE_ENEMY_TRAIL = ConfigItem('挑战-收割')
    ENCOUNTER = ConfigItem('偶遇事件')
    PRICE_DIFFERENCE = ConfigItem('代价之间')
    REST = ConfigItem('休憩调息')
    BANGBOO_STORE = ConfigItem('邦布商店')
    FRIENDLY_TALK = ConfigItem('挚交会谈')
    ELITE = ConfigItem('战斗-道中危机')
    BOSS = ConfigItem('战斗-终结之役')

    @classmethod
    def from_value(cls, value: str):
        for name in LostVoidRegionType.__members__:
            enum = cls[name]
            if enum.value.value == value:
                return enum
        return LostVoidRegionType.ENTRY


class LostVoidPeriodBuffNo(Enum):

    NO_1 = ConfigItem('第一个')
    NO_2 = ConfigItem('第二个')
    NO_3 = ConfigItem('第三个')


class LostVoidBuyOnlyPriority(Enum):

    NONE = ConfigItem('刷新0次', value=0)
    NO_1 = ConfigItem('刷新1次(50硬币)', value=1)
    NO_2 = ConfigItem('刷新2次(100硬币)', value=2)
    NO_3 = ConfigItem('刷新3次(200硬币)', value=3)
    NO_4 = ConfigItem('刷新4次(300硬币)', value=4)
    ALWAYS = ConfigItem('一直刷新', value=999)


class LostVoidChallengeConfig(YamlConfig):

    def __init__(self, module_name: str, is_mock: bool = False):
        YamlConfig.__init__(
            self,
            module_name,
            sub_dir=['lost_void_challenge'],
            is_mock=is_mock, sample=True, copy_from_sample=False,
        )

        self.old_module_name: str = self.module_name
        self.old_file_path: str = self.file_path

    def copy_new(self) -> None:
        """
        复制变成一个新的
        :return:
        """
        self.module_name = self.module_name + '_copy'
        self.old_module_name = self.module_name
        self.remove_sample()

    def remove_sample(self) -> None:
        """
        设置为不是sample
        :return:
        """
        self._sample = False
        self.file_path = self._get_yaml_file_path()

    def update_module_name(self, value: str) -> None:
        """
        更新模块名称
        :param value: 新名字
        """
        self.module_name = value
        self._sample = False

        self.save()

    def save(self) -> None:
        if self.old_module_name != self.module_name:
            # 删除旧文件
            os.remove(self.old_file_path)
            self.file_path = self._get_yaml_file_path()

        self.old_module_name = self.module_name
        self.old_file_path = self.file_path
        YamlConfig.save(self)

    @property
    def predefined_team_idx(self) -> int:
        # 预备配队下标 -1为使用当前配队
        return self.get('predefined_team_idx', -1)

    @predefined_team_idx.setter
    def predefined_team_idx(self, new_value: int):
        self.update('predefined_team_idx', new_value)

    @property
    def choose_team_by_priority(self) -> bool:
        """
        当副本有当期UP时 优先选择相关配队
        :return:
        """
        return self.get('choose_team_by_priority', False)

    @choose_team_by_priority.setter
    def choose_team_by_priority(self, new_value: bool):
        self.update('choose_team_by_priority', new_value)

    @property
    def auto_battle(self) -> str:
        return self.get('auto_battle', '全配队通用')

    @auto_battle.setter
    def auto_battle(self, new_value: str):
        self.update('auto_battle', new_value)

    @property
    def artifact_priority_new(self) -> bool:
        """
        优先选择NEW!藏品
        :return:
        """
        return self.get('artifact_priority_new', False)

    @artifact_priority_new.setter
    def artifact_priority_new(self, new_value: bool):
        self.update('artifact_priority_new', new_value)

    @property
    def artifact_priority(self) -> List[str]:
        return self.get('artifact_priority', [])

    @artifact_priority.setter
    def artifact_priority(self, new_value: List[str]):
        self.update('artifact_priority', new_value)

    @property
    def artifact_priority_str(self) -> str:
        return '\n'.join(self.artifact_priority)

    @property
    def artifact_priority_2(self) -> List[str]:
        return self.get('artifact_priority_2', [])

    @artifact_priority_2.setter
    def artifact_priority_2(self, new_value: List[str]):
        self.update('artifact_priority_2', new_value)

    @property
    def artifact_priority_2_str(self) -> str:
        return '\n'.join(self.artifact_priority_2)

    @property
    def region_type_priority(self) -> List[str]:
        return self.get('region_type_priority', [])

    @region_type_priority.setter
    def region_type_priority(self, new_value: List[str]):
        self.update('region_type_priority', new_value)

    @property
    def region_type_priority_str(self) -> str:
        return '\n'.join(self.region_type_priority)

    @property
    def period_buff_no(self) -> str:
        return self.get('period_buff_no', LostVoidPeriodBuffNo.NO_1.value.value)

    @period_buff_no.setter
    def period_buff_no(self, new_value: str):
        self.update('period_buff_no', new_value)

    @property
    def buy_only_priority_1(self) -> int:
        return self.get('buy_only_priority_1', 1)

    @buy_only_priority_1.setter
    def buy_only_priority_1(self, new_value: int):
        self.update('buy_only_priority_1', new_value)

    @property
    def buy_only_priority_2(self) -> int:
        return self.get('buy_only_priority_2', 3)

    @buy_only_priority_2.setter
    def buy_only_priority_2(self, new_value: int):
        self.update('buy_only_priority_2', new_value)

    @property
    def store_blood(self) -> bool:
        """
        @return: 是否使用血量购买商店
        """
        return self.get('store_blood', False)

    @store_blood.setter
    def store_blood(self, new_value: bool):
        self.update('store_blood', new_value)

    @property
    def store_blood_min(self) -> int:
        """
        @return: 大于等于多少血量时 才会选择刷新和购买
        """
        return self.get('store_blood_min', 50)

    @store_blood_min.setter
    def store_blood_min(self, new_value: int):
        self.update('store_blood_min', new_value)

    @property
    def investigation_strategy(self) -> str:
        return self.get('investigation_strategy', '鸣徽狂热战略')

    @investigation_strategy.setter
    def investigation_strategy(self, new_value: str):
        self.update('investigation_strategy', new_value)


def get_all_lost_void_challenge_config(with_sample: bool = True) -> List[LostVoidChallengeConfig]:
    config_list: List[LostVoidChallengeConfig] = []
    dir_path = os_utils.get_path_under_work_dir('config', 'lost_void_challenge')
    config_name_list = os.listdir(dir_path)
    existed_module_set = set()
    for config_name in config_name_list:
        if not config_name.endswith('.yml'):
            continue
        if config_name.endswith('.sample.yml'):
            if not with_sample:
                continue
            module_name = config_name[:-11]
        else:
            module_name = config_name[:-4]

        if module_name in existed_module_set:
            continue
        existed_module_set.add(module_name)

        try:
            config = LostVoidChallengeConfig(module_name)
            config_list.append(config)
        except Exception:
            log.error('配置文件读取错误 跳过 %s', config_name)
    return config_list


def get_lost_void_challenge_new_name() -> str:
    """
    获取新的配置文件的命名
    :return:
    """
    prefix: str = '自定义-'
    max_idx: int = 0
    dir_path = os_utils.get_path_under_work_dir('config', 'lost_void_challenge')
    config_name_list = os.listdir(dir_path)
    for config_name in config_name_list:
        if not config_name.endswith('.yml'):
            continue
        if not config_name.startswith(prefix):
            continue
        try:
            idx = int(config_name[len(prefix):-4])
            if idx > max_idx:
                max_idx = idx
        except Exception:
            pass

    return '%s%02d' % (prefix, max_idx + 1)