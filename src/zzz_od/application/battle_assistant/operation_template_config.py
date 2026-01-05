import os

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils import os_utils


def get_operation_template_config_list() -> list[ConfigItem]:
    """
    获取用于配置页面显示的指令列表，支持子目录。
    :return: 配置页面的选项列表
    """
    auto_battle_dir_path = os_utils.get_path_under_work_dir('config', 'auto_battle_operation')

    template_name_set = set()

    # 递归查找所有 .yml 文件
    for root, dirs, files in os.walk(auto_battle_dir_path):
        for file_name in files:
            if file_name.endswith('.sample.yml'):
                template_name = os.path.join(root, file_name[:-11])  # 去掉 '.sample.yml'
            elif file_name.endswith('.yml'):
                template_name = os.path.join(root, file_name[:-4])  # 去掉 '.yml'
            else:
                continue

            # 转换为相对路径
            relative_template_name = os.path.relpath(template_name, auto_battle_dir_path).replace("\\", "/")
            template_name_set.add(relative_template_name)

    # 将 template_name_set 转换为列表并排序
    sorted_template_names = sorted(template_name_set, key=lambda x: x.lower())

    return [ConfigItem(label=op, value=op) for op in sorted_template_names]
