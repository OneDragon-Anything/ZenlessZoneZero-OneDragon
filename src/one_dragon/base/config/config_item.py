from collections.abc import Iterable
from enum import Enum
from typing import Any

from one_dragon.utils.i18_utils import gt


class ConfigItem:

    def __init__(self, label: str, value: Any = None, desc: str | None = None,
                 tag: str | None = None):
        """
        选项值
        :param label: 显示文本
        :param value: 真实值
        :param desc: 选项解释
        :param tag: 选中该选项时，在设置卡片上显示的小标签文本（如「前台」「后台」）
        """
        self.label: str = label  # 显示文本
        self.value: Any = label if value is None else value  # 值
        self.desc: str = desc if desc is not None else ''  # 选项解释
        self.tag: str = tag if tag is not None else ''  # 小标签

    @property
    def ui_text(self) -> str:
        """
        显示的文本
        :return:
        """
        return gt(self.label)


def get_config_item_from_enum(enum: Iterable[Enum], value: Any) -> ConfigItem | None:
    """
    从一个配置枚举中 获取目标配置
    :param enum: 枚举
    :param value: 配置值
    :return:
    """
    for item in enum:
        if not isinstance(item.value, ConfigItem):
            continue
        config_item: ConfigItem = item.value
        if config_item.value == value:
            return config_item
    return None
