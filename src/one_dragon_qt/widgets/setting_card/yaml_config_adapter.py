from typing import Any, Optional

from one_dragon.base.config.yaml_operator import YamlOperator


class YamlConfigAdapter:

    def __init__(self, config: YamlOperator, field: str, default_val: Any = None,
                 getter_convert: Optional[str] = None,
                 setter_convert: Optional[str] = None):
        self.config: YamlOperator = config
        self.field: str = field
        self.default_val: Any = default_val
        self.getter_convert: Optional[str] = getter_convert
        self.setter_convert: Optional[str] = setter_convert

    def get_value(self) -> Any:
        # 获取self.field对应的property属性的值
        val = getattr(self.config, self.field)
        if self.getter_convert == 'str':
            return str(val)
        elif self.getter_convert == 'int':
            return int(val)
        elif self.getter_convert == 'float':
            return float(val)
        else:
            return val

    def set_value(self, new_value: Any) -> None:
        if self.setter_convert == 'str':
            val = str(new_value)
        elif self.setter_convert == 'int':
            val = int(new_value)
        elif self.setter_convert == 'float':
            val = float(new_value)
        else:
            val = new_value

        self.config.update(self.field, val)
