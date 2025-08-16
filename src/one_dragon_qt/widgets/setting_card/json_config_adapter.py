from typing import Optional, Any, Callable

from one_dragon.base.config.json_config import JsonConfig
from one_dragon.module.logger import logger


class JsonConfigAdapter():
    """
    JSON配置适配器，用于在GUI组件和JSON配置文件之间建立桥梁
    """

    def __init__(self, config: JsonConfig, field: str, default_val: Any = None,
                 getter_convert: Optional[str] = None,
                 setter_convert: Optional[str] = None):
        """
        初始化JSON配置适配器
        :param config: JSON配置对象
        :param field: 配置字段名，支持嵌套格式如 "settings.display.theme"
        :param default_val: 默认值，当配置项不存在时返回
        :param getter_convert: 获取值时的转换器名称
        :param setter_convert: 设置值时的转换器名称
        """
        self.config = config
        self.field = field
        self.default_val = default_val
        self._getter_convert = getter_convert
        self._setter_convert = setter_convert

    def get_value(self) -> Any:
        """
        获取配置值，支持嵌套路径
        :return: 配置值
        """
        try:
            # 检查是否是属性访问
            if hasattr(self.config, self.field):
                value = getattr(self.config, self.field)
            else:
                # 处理嵌套路径
                if '.' in self.field:
                    # 使用 deep_get 处理嵌套结构
                    value = self._deep_get(self.field)
                else:
                    # 普通字段直接获取
                    value = self.config.get(self.field)
                
                # 如果值为None且有默认值，返回默认值
                if value is None and self.default_val is not None:
                    value = self.default_val
            
            # 应用转换器
            if self._getter_convert:
                value = self._convert_value(value, self._getter_convert)
                
            return value
        except Exception as e:
            logger.error(f"获取配置值失败: {self.field}, 错误: {str(e)}")
            return self.default_val

    def set_value(self, value: Any) -> bool:
        """
        设置配置值，支持嵌套路径
        :param value: 要设置的值
        :return: 是否设置成功
        """
        try:
            # 应用转换器
            if self._setter_convert:
                value = self._convert_value(value, self._setter_convert)
            
            # 处理嵌套路径
            if '.' in self.field:
                # 使用 deep_update 处理嵌套结构
                success = self._deep_update(self.field, value)
            else:
                # 普通字段直接更新
                self.config.update(self.field, value)
                success = True
                
            return success
        except Exception as e:
            logger.error(f"设置配置值失败: {self.field}, 值: {value}, 错误: {str(e)}")
            return False

    def _deep_get(self, path: str) -> Any:
        """
        获取嵌套JSON中的值
        :param path: 点号分隔的路径，如 "settings.display.theme"
        :return: 找到的值，如果路径不存在则返回None
        """
        keys = path.split('.')
        data = self.config.data
        
        for key in keys:
            if data is None or not isinstance(data, dict) or key not in data:
                return None
            data = data[key]
            
        return data

    def _deep_update(self, path: str, value: Any) -> bool:
        """
        更新嵌套JSON中的值
        :param path: 点号分隔的路径，如 "settings.display.theme"
        :param value: 要设置的值
        :return: 是否更新成功
        """
        # 如果配置对象有 deep_update 方法，直接使用
        if hasattr(self.config, 'deep_update'):
            return self.config.deep_update(path, value)
        
        # 否则手动实现嵌套更新
        keys = path.split('.')
        data = self.config.data
        
        # 确保数据是字典
        if data is None:
            self.config.data = {}
            data = self.config.data
        
        # 遍历路径，创建必要的嵌套字典
        current = data
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        
        # 设置最终值
        current[keys[-1]] = value
        
        # 保存更改
        self.config.save()
        return True

    def _convert_value(self, value: Any, convert_type: str) -> Any:
        """
        根据指定的转换类型转换值
        :param value: 要转换的值
        :param convert_type: 转换类型
        :return: 转换后的值
        """
        if convert_type == 'str':
            return str(value) if value is not None else ""
        elif convert_type == 'int':
            try:
                return int(value) if value is not None else 0
            except (ValueError, TypeError):
                return 0
        elif convert_type == 'float':
            try:
                return float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        elif convert_type == 'bool':
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', 'yes', '1', 'y', 'on')
            return bool(value)
        elif convert_type == 'list':
            if value is None:
                return []
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                return value.split(',')
            return [value]
        else:
            return value 