import os
import shutil
from typing import Optional, List

from one_dragon.base.config.json_operator import JsonOperator
from one_dragon.utils import os_utils


class JsonConfig(JsonOperator):

    def __init__(self,
                 module_name: str,
                 instance_idx: Optional[int] = None,
                 sub_dir: Optional[List[str]] = None,
                 sample: bool = False,
                 mock: bool = False):
        self.instance_idx: Optional[int] = instance_idx
        """传入时 该配置为一个的脚本实例独有的配置"""

        self.sub_dir: Optional[List[str]] = sub_dir
        """配置所在的子目录"""

        self.module_name: str = module_name
        """配置文件名称"""

        self.mock: bool = mock
        """mock情况下 不读取文件 也不会实际保存 用于测试"""

        JsonOperator.__init__(self, self._get_json_file_path(sample))

    def _get_json_file_path(self, sample: bool = False) -> Optional[str]:
        """
        获取配置文件的路径
        如果只有sample文件，就复制一个到实例文件夹下
        :param sample: 是否有sample文件
        :return:
        """
        if self.mock:
            return None
        sub_dir = ['config']
        if self.instance_idx is not None:
            sub_dir.append('%02d' % self.instance_idx)
        if self.sub_dir is not None:
            sub_dir = sub_dir + self.sub_dir

        yml_path = os.path.join(os_utils.get_path_under_work_dir(*sub_dir), f'{self.module_name}.json')
        sample_yml_path = os.path.join(os_utils.get_path_under_work_dir(*sub_dir), f'{self.module_name}.sample.json')
        path = sample_yml_path if sample and not os.path.exists(yml_path) else yml_path
        use_sample = sample and not os.path.exists(yml_path)

        if use_sample:
            shutil.copyfile(sample_yml_path, yml_path)

        return yml_path
    
    def get_prop_adapter(self, prop: str,
                         getter_convert: Optional[str] = None,
                         setter_convert: Optional[str] = None):
        """
        获取一个配置适配器
        :param prop: 配置字段
        :param getter_convert: 获取时的转换器
        :param setter_convert: 设置时的转换器
        :return: JSON配置适配器
        """
        from one_dragon_qt.widgets.setting_card.json_config_adapter import JsonConfigAdapter
        return JsonConfigAdapter(
            config=self,
            field=prop,
            getter_convert=getter_convert,
            setter_convert=setter_convert
        )
    
    
