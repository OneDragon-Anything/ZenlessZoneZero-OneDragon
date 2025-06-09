from functools import wraps
from typing import Any, Callable, Set, Optional


class PropertyInfo:
    """属性信息描述类"""

    def __init__(self,
                 property_type: str,
                 cache_attr_name: str,
                 category: Optional[str] = None,
                 description: Optional[str] = None):
        """
        属性信息
        :param property_type: 属性类型 'config' 或 'record'
        :param cache_attr_name: 缓存属性名
        :param category: 属性分类
        :param description: 属性描述
        """
        self.property_type: str = property_type
        """属性类型 config/record"""

        self.cache_attr_name: str = cache_attr_name
        """缓存属性名"""

        self.category: Optional[str] = category
        """属性分类"""

        self.description: Optional[str] = description
        """属性描述"""


class PropertyGroup:
    """Property分组管理器"""

    def __init__(self):
        self.config_properties: Set[str] = set()
        """配置属性集合"""

        self.record_properties: Set[str] = set()
        """运行记录属性集合"""

        self.all_properties: dict[str, PropertyInfo] = {}
        """所有属性信息字典"""

    def register_property(self, property_info: PropertyInfo) -> None:
        """
        注册属性信息
        :param property_info: 属性信息
        """
        cache_attr = property_info.cache_attr_name
        self.all_properties[cache_attr] = property_info

        if property_info.property_type == 'config':
            self.config_properties.add(cache_attr)
        elif property_info.property_type == 'record':
            self.record_properties.add(cache_attr)

    def config_property(self, func: Callable) -> property:
        """配置属性装饰器"""
        prop_name = f"_{func.__name__}"
        self.config_properties.add(prop_name)
        return property(func)

    def record_property(self, func: Callable) -> property:
        """运行记录属性装饰器"""
        prop_name = f"_{func.__name__}"
        self.record_properties.add(prop_name)
        return property(func)

    def clear_configs(self, obj: Any) -> None:
        """清理所有配置属性"""
        for attr in self.config_properties:
            if hasattr(obj, attr):
                delattr(obj, attr)

    def clear_records(self, obj: Any) -> None:
        """清理所有运行记录属性"""
        for attr in self.record_properties:
            if hasattr(obj, attr):
                delattr(obj, attr)


def config_property(category: Optional[str] = None, description: Optional[str] = None):
    """
    配置属性装饰器
    :param category: 属性分类
    :param description: 属性描述
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            return func(self)

        # 生成缓存属性名
        cache_attr_name = f"_{func.__name__}"

        # 创建属性信息
        property_info = PropertyInfo(
            property_type='config',
            cache_attr_name=cache_attr_name,
            category=category,
            description=description
        )

        # 注册到全局实例
        property_group.register_property(property_info)

        # 在装饰器的注解中存储属性信息
        wrapper.__annotations__['property_annotation'] = property_info

        return property(wrapper)
    return decorator


def record_property(category: Optional[str] = None, description: Optional[str] = None):
    """
    运行记录属性装饰器
    :param category: 属性分类
    :param description: 属性描述
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            return func(self)

        # 生成缓存属性名
        cache_attr_name = f"_{func.__name__}"

        # 创建属性信息
        property_info = PropertyInfo(
            property_type='record',
            cache_attr_name=cache_attr_name,
            category=category,
            description=description
        )

        # 注册到全局实例
        property_group.register_property(property_info)

        # 在装饰器的注解中存储属性信息
        wrapper.__annotations__['property_annotation'] = property_info

        return property(wrapper)
    return decorator


# 全局实例
property_group = PropertyGroup()
