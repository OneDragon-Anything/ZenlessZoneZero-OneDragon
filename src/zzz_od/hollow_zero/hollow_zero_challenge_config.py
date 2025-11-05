import os
from enum import Enum
from typing import List

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.utils import os_utils
from one_dragon.utils.log_utils import log


class HollowZeroChallengePathFinding(Enum):

    DEFAULT = ConfigItem('默认', desc='默认的寻路方式')
    ONLY_BOSS = ConfigItem('速通', desc='途经呼叫增援和业绩考察点 避免战斗')
    CUSTOM = ConfigItem('自定义', desc='自己在下边填吧 名称可以看游戏图鉴')


class HollowZeroChallengeConfig(YamlConfig):

    def __init__(self, module_name: str, is_mock: bool = False):
        YamlConfig.__init__(
            self,
            module_name,
            sub_dir=['hollow_zero_challenge'],
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
    def auto_battle(self) -> str:
        return self.get('auto_battle', '全配队通用')

    @auto_battle.setter
    def auto_battle(self, new_value: str):
        self.update('auto_battle', new_value)

    @property
    def resonium_priority(self) -> List[str]:
        return self.get('resonium_priority', [])

    @resonium_priority.setter
    def resonium_priority(self, new_value: List[str]):
        self.update('resonium_priority', new_value)

    @property
    def resonium_priority_str(self) -> str:
        return '\n'.join(self.resonium_priority)

    @property
    def event_priority(self) -> List[str]:
        return self.get('event_priority', [])

    @event_priority.setter
    def event_priority(self, new_value: List[str]):
        self.update('event_priority', new_value)

    @property
    def event_priority_str(self) -> str:
        return '\n'.join(self.event_priority)

    @property
    def target_agents(self) -> List[str]:
        return self.get('target_agents', [None, None, None])

    @target_agents.setter
    def target_agents(self, new_value: List[str]):
        self.update('target_agents', new_value)

    @property
    def path_finding(self) -> str:
        return self.get('path_finding', HollowZeroChallengePathFinding.DEFAULT.value.value)

    @path_finding.setter
    def path_finding(self, new_value: str):
        self.update('path_finding', new_value)

    @property
    def go_in_1_step(self) -> List[str]:
        """
        一步可达时前往
        :return:
        """
        return self.get('go_in_1_step', [])

    @go_in_1_step.setter
    def go_in_1_step(self, new_value: List[str]):
        self.update('go_in_1_step', new_value)

    @property
    def waypoint(self) -> List[str]:
        """
        途经点
        :return:
        """
        return self.get('waypoint', [])

    @waypoint.setter
    def waypoint(self, new_value: List[str]):
        self.update('waypoint', new_value)

    @property
    def avoid(self) -> List[str]:
        """
        避免
        :return:
        """
        return self.get('avoid', [])

    @avoid.setter
    def avoid(self, new_value: List[str]):
        self.update('avoid', new_value)

    @property
    def buy_only_priority(self) -> bool:
        """
        只购买优先级中的内容
        :return:
        """
        return self.get('buy_only_priority', True)

    @buy_only_priority.setter
    def buy_only_priority(self, new_value: bool):
        self.update('buy_only_priority', new_value)



def get_all_hollow_zero_challenge_config(with_sample: bool = True) -> List[HollowZeroChallengeConfig]:
    config_list: List[HollowZeroChallengeConfig] = []
    dir_path = os_utils.get_path_under_work_dir('config', 'hollow_zero_challenge')
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
            config = HollowZeroChallengeConfig(module_name)
            config_list.append(config)
        except Exception:
            log.error('配置文件读取错误 跳过 %s', config_name)
    return config_list


def get_hollow_zero_challenge_new_name() -> str:
    """
    获取新的配置文件的命名
    :return:
    """
    prefix: str = '自定义-'
    max_idx: int = 0
    dir_path = os_utils.get_path_under_work_dir('config', 'hollow_zero_challenge')
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
