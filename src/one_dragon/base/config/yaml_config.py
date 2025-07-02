import os
import shutil
from typing import Optional, List

from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon.utils import os_utils


class YamlConfig(YamlOperator):

    def __init__(
            self,
            module_name: str,
            backup_model_name: str | None = None,
            instance_idx: Optional[int] = None,
            sub_dir: Optional[List[str]] = None,
            sample: bool = False, copy_from_sample: bool = False,
            is_mock: bool = False
    ):
        self.instance_idx: Optional[int] = instance_idx
        """传入时 该配置为一个的脚本实例独有的配置"""

        self.sub_dir: Optional[List[str]] = sub_dir
        """配置所在的子目录"""

        self.module_name: str = module_name
        """配置文件名称"""

        self.backup_model_name: str = backup_model_name
        """备用的配置文件名称 主要用于配置文件改名时做迁移使用"""

        self.is_mock: bool = is_mock
        """mock情况下 不读取文件 也不会实际保存 用于测试"""

        self._sample: bool = sample
        """是否有sample文件"""

        self._copy_from_sample: bool = copy_from_sample
        """配置文件不存在时 是否从sample文件中读取"""

        YamlOperator.__init__(self, self._get_yaml_file_path())

    def _get_yaml_file_path(self) -> Optional[str]:
        """
        获取配置文件的路径
        如果只有sample文件，就复制一个到实例文件夹下
        :return:
        """
        if self.is_mock:
            return None
        sub_dir = ['config']
        if self.instance_idx is not None:
            sub_dir.append('%02d' % self.instance_idx)
        if self.sub_dir is not None:
            sub_dir = sub_dir + self.sub_dir

        dir_path = os_utils.get_path_under_work_dir(*sub_dir)

        # 指定文件存在时 直接使用
        yml_path = os.path.join(dir_path, f'{self.module_name}.yml')
        if os.path.exists(yml_path):
            return yml_path

        # 备用文件存在时 复制使用
        backup_yml_path = os.path.join(dir_path, f'{self.backup_model_name}.yml')
        if os.path.exists(backup_yml_path):
            shutil.copyfile(backup_yml_path, yml_path)
            return yml_path

        # 最后看是否有示例文件
        sample_yml_path = os.path.join(dir_path, f'{self.module_name}.sample.yml')
        if self._sample and self._copy_from_sample and os.path.exists(sample_yml_path):
            shutil.copyfile(sample_yml_path, yml_path)
            return yml_path

        return yml_path

    @property
    def is_sample(self) -> bool:
        """
        是否样例文件
        :return:
        """
        return self.file_path.endswith('.sample.yml')

    def get_prop_adapter(self, prop: str,
                         getter_convert: Optional[str] = None,
                         setter_convert: Optional[str] = None):
        """
        获取一个配置适配器
        :param prop: 配置字段
        :param getter_convert: 获取时的转换器
        :param setter_convert: 设置时的转换器
        :return:
        """
        from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter
        return YamlConfigAdapter(
            config=self,
            field=prop,
            getter_convert=getter_convert,
            setter_convert=setter_convert
        )
