from typing import Optional

from one_dragon.base.config.config_adapter import ConfigAdapter
from one_dragon.base.config.yaml_operator import YamlOperator


def get_prop_adapter(
    config: YamlOperator,
    prop: str,
    getter_convert: Optional[str] = None,
    setter_convert: Optional[str] = None,
) -> ConfigAdapter:
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

    return ConfigAdapter(
        config=config,
        field=prop,
        getter_convert=getter_convert,
        setter_convert=setter_convert,
    )
