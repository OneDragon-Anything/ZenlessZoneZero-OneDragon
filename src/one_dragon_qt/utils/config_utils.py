from typing import Optional

from one_dragon.base.config.yaml_operator import YamlOperator
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


def get_prop_adapter(
    config: YamlOperator,
    prop: str,
    getter_convert: Optional[str] = None,
    setter_convert: Optional[str] = None,
) -> YamlConfigAdapter:
    """
    获取一个属性适配器

    Args:
        config: 来源配置
        prop: 属性名称
        getter_convert: 获取属性时使用的转化器
        setter_convert: 设置属性时使用的转化器

    Returns:
        属性适配器
    """

    return YamlConfigAdapter(
        config=config,
        field=prop,
        getter_convert=getter_convert,
        setter_convert=setter_convert,
    )