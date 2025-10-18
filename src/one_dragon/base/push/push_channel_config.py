"""
推送通道配置数据结构定义

定义推送通道的字段配置和通道配置的数据结构，用于抽象和规范化不同推送服务的配置参数。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional


class FieldTypeEnum(Enum):
    """字段类型枚举，定义支持的UI组件类型"""
    TEXT = "text"
    COMBO = "combo"
    KEY_VALUE = "key_value"
    CODE_EDITOR = "code_editor"


@dataclass
class PushChannelConfigField:
    """
    推送通道字段配置

    表示推送通道中单个配置字段的元数据，包括字段名、类型、验证规则等。
    """
    var_suffix: str
    title: str
    icon: str
    field_type: FieldTypeEnum = FieldTypeEnum.TEXT
    placeholder: str = ''
    required: bool = False
    options: list[str] = field(default_factory=list)
    default: str = ''
    language: Optional[str] = None  # 代码编辑器的语言类型
