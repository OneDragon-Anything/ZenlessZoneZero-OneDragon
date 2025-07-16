import os
import shutil
from enum import Enum
from typing import List, Optional

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig
from one_dragon.utils import os_utils


class RunInOneDragonApp(Enum):

    RUN = ConfigItem('一条龙中运行', value=True)
    DONT_RUN = ConfigItem('一条龙中不运行', value=False)


class OneDragonInstance:

    def __init__(self, idx: int, name: str, active: bool, active_in_od: bool):
        self.idx: int = idx
        self.name: str = name
        self.active: bool = active
        self.active_in_od: bool = active_in_od


class AfterDoneOpEnum(Enum):

    NONE = ConfigItem('无')
    CLOSE_GAME = ConfigItem('关闭游戏')
    SHUTDOWN = ConfigItem('关机')


class InstanceRun(Enum):

    ALL = ConfigItem('全部实例')
    CURRENT = ConfigItem('仅运行当前')


class OneDragonConfig(YamlConfig):

    def __init__(self):
        YamlConfig.__init__(self, 'one_dragon', backup_model_name='zzz_one_dragon')  # TODO 2025.12时可以删掉 backup_model_name
        self.instance_list: List[OneDragonInstance] = []
        self._temp_instance_indices: Optional[List[int]] = None
        self._init_instance_list()

    def set_temp_instance_indices(self, instance_indices: Optional[List[int]]):
        """设置临时实例索引列表"""
        self._temp_instance_indices = instance_indices

    def clear_temp_instance_indices(self):
        """清除临时实例索引列表"""
        self._temp_instance_indices = None

    def _init_instance_list(self):
        """
        初始化账号列表
        :return:
        """
        instance_list = self.dict_instance_list

        self.instance_list.clear()
        for instance in instance_list:
            i = OneDragonInstance(**instance)
            self.instance_list.append(i)

    def create_new_instance(self, first: bool) -> OneDragonInstance:
        """
        创建一个新的脚本账号
        :param first:
        :return:
        """
        idx = 0
        while True:
            idx += 1
            existed: bool = False
            for instance in self.instance_list:
                if instance.idx == idx:
                    existed = True
                    break
            if not existed:
                break

        new_instance = OneDragonInstance(idx, '%02d' % idx, first, True)
        self.instance_list.append(new_instance)

        dict_instance_list = self.dict_instance_list
        dict_instance_list.append(vars(new_instance))
        self.dict_instance_list = dict_instance_list

        return new_instance

    def update_instance(self, to_update: OneDragonInstance):
        """
        更新一个账号
        :param to_update:
        :return:
        """
        dict_instance_list = self.dict_instance_list

        for instance in dict_instance_list:
            if instance['idx'] == to_update.idx:
                instance['name'] = to_update.name
                instance['active_in_od'] = to_update.active_in_od

        self.save()
        self._init_instance_list()

    def active_instance(self, instance_idx: int):
        """
        启用一个账号
        :param instance_idx:
        :return:
        """
        dict_instance_list = self.dict_instance_list

        for instance in dict_instance_list:
            instance['active'] = instance['idx'] == instance_idx

        self.save()
        self._init_instance_list()

    def delete_instance(self, instance_idx: int):
        """
        删除一个账号
        :param instance_idx:
        :return:
        """
        idx = -1

        dict_instance_list = self.dict_instance_list
        for i in range(len(dict_instance_list)):
            if dict_instance_list[i]['idx'] == instance_idx:
                idx = i
                break
        if idx != -1:
            dict_instance_list.pop(idx)
        self.dict_instance_list = dict_instance_list

        instance_dir = os_utils.get_path_under_work_dir('config', ('%02d' % instance_idx))
        if os.path.exists(instance_dir):
            shutil.rmtree(instance_dir)

        self.save()
        self._init_instance_list()

    @property
    def dict_instance_list(self) -> List[dict]:
        return self.get('instance_list', [])

    @dict_instance_list.setter
    def dict_instance_list(self, new_list: List[dict]):
        self.update('instance_list', new_list)

    @property
    def current_active_instance(self) -> Optional[OneDragonInstance]:
        """
        获取当前激活使用的账号
        :return:
        """
        for instance in self.instance_list:
            if instance.active:
                return instance
        return None

    @property
    def instance_list_in_od(self) -> List[OneDragonInstance]:
        """
        需要在一条龙中运行的实例列表
        如果设置了临时实例索引，则使用临时配置
        :return:
        """
        if self._temp_instance_indices is not None:
            return [instance for instance in self.instance_list if instance.idx in self._temp_instance_indices]
        return [instance for instance in self.instance_list if instance.active_in_od]

    @property
    def instance_run(self) -> str:
        return self.get('instance_run', InstanceRun.ALL.value.value)

    @instance_run.setter
    def instance_run(self, new_value: str):
        self.update('instance_run', new_value)

    @property
    def after_done(self) -> str:
        return self.get('after_done', AfterDoneOpEnum.NONE.value.value)

    @after_done.setter
    def after_done(self, new_value: str):
        self.update('after_done', new_value)
