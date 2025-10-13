import os
from typing import List, Optional

from one_dragon.base.conditional_operation.conditional_operator import ConditionalOperator
from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils import os_utils


def get_auto_battle_op_config_list(sub_dir: str) -> List[ConfigItem]:
    """
    获取用于配置页面显示的指令列表
    :return:
    """
    auto_battle_dir_path = os_utils.get_path_under_work_dir('config', sub_dir)

    template_name_set = set()
    for file_name in os.listdir(auto_battle_dir_path):
        if file_name.endswith('.sample.yml'):
            template_name = file_name[:-11]
        elif file_name.endswith('.yml'):
            template_name = file_name[:-4]
        else:
            continue

        template_name_set.add(template_name)

    # 将 template_name_set 转换为列表并排序
    sorted_template_names = sorted(template_name_set, key=lambda x: x.lower())

    return [ConfigItem(label=template_name, value=template_name)
            for template_name in sorted_template_names]


def get_all_auto_battle_op(sub_dir: str) -> List[ConditionalOperator]:
    """
    加载所有的自动战斗指令
    :return:
    """
    config_list = get_auto_battle_op_config_list(sub_dir)
    result_op_list = []
    for config in config_list:
        result_op_list.append(ConditionalOperator(sub_dir, config.value))

    return result_op_list


def get_auto_battle_op_by_name(sub_dir: str, template_name: str) -> Optional[ConditionalOperator]:
    config_list = get_auto_battle_op_config_list(sub_dir)
    for config in config_list:
        if config.value == template_name:
            return ConditionalOperator(sub_dir, template_name)
    return None


def get_auto_battle_config_file_path(sub_dir: str, template_name: str) -> str:
    """
    自动战斗配置文件路径
    :param sub_dir: 目录名称
    :param template_name: 模板名称
    :return:
    """
    return os.path.join(
        os_utils.get_path_under_work_dir('config', sub_dir),
        f'{template_name}.yml'
    )
