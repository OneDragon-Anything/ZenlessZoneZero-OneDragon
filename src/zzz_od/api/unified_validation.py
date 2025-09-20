"""
统一API输入验证模块

提供标准化的输入验证和安全防护机制
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from .unified_errors import ValidationException, APIErrorCode


class InputValidator:
    """输入验证器"""

    # 常用正则表达式
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    CONFIG_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9\u4e00-\u9fff_\-\s]{1,100}$')
    MODULE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]{1,50}$')

    @staticmethod
    def validate_required(value: Any, field_name: str) -> None:
        """验证必填字段"""
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationException(
                f"{field_name}不能为空",
                {"field": field_name, "value": value}
            )

    @staticmethod
    def validate_string_length(
        value: str,
        field_name: str,
        min_length: int = 0,
        max_length: int = 1000
    ) -> None:
        """验证字符串长度"""
        if not isinstance(value, str):
            raise ValidationException(
                f"{field_name}必须是字符串",
                {"field": field_name, "value": value, "expected_type": "string"}
            )

        if len(value) < min_length:
            raise ValidationException(
                f"{field_name}长度不能少于{min_length}个字符",
                {"field": field_name, "value": value, "min_length": min_length}
            )

        if len(value) > max_length:
            raise ValidationException(
                f"{field_name}长度不能超过{max_length}个字符",
                {"field": field_name, "value": value, "max_length": max_length}
            )

    @staticmethod
    def validate_numeric_range(
        value: Union[int, float],
        field_name: str,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None
    ) -> None:
        """验证数值范围"""
        if not isinstance(value, (int, float)):
            raise ValidationException(
                f"{field_name}必须是数值",
                {"field": field_name, "value": value, "expected_type": "number"}
            )

        if min_value is not None and value < min_value:
            raise ValidationException(
                f"{field_name}不能小于{min_value}",
                {"field": field_name, "value": value, "min_value": min_value}
            )

        if max_value is not None and value > max_value:
            raise ValidationException(
                f"{field_name}不能大于{max_value}",
                {"field": field_name, "value": value, "max_value": max_value}
            )

    @staticmethod
    def validate_uuid(value: str, field_name: str) -> None:
        """验证UUID格式"""
        if not isinstance(value, str):
            raise ValidationException(
                f"{field_name}必须是字符串",
                {"field": field_name, "value": value}
            )

        if not InputValidator.UUID_PATTERN.match(value):
            raise ValidationException(
                f"{field_name}格式不正确，必须是有效的UUID",
                {"field": field_name, "value": value}
            )

    @staticmethod
    def validate_config_name(value: str, field_name: str = "配置名称") -> None:
        """验证配置名称"""
        InputValidator.validate_required(value, field_name)
        InputValidator.validate_string_length(value, field_name, 1, 100)

        if not InputValidator.CONFIG_NAME_PATTERN.match(value):
            raise ValidationException(
                f"{field_name}只能包含中文、英文、数字、下划线、连字符和空格",
                {"field": field_name, "value": value}
            )

        # 检查危险字符
        dangerous_chars = ['<', '>', '"', "'", '&', '\\', '/', '|', '*', '?', ':']
        for char in dangerous_chars:
            if char in value:
                raise ValidationException(
                    f"{field_name}包含非法字符: {char}",
                    {"field": field_name, "value": value, "illegal_char": char}
                )

    @staticmethod
    def validate_module_name(value: str, field_name: str = "模块名称") -> None:
        """验证模块名称"""
        InputValidator.validate_required(value, field_name)
        InputValidator.validate_string_length(value, field_name, 1, 50)

        if not InputValidator.MODULE_NAME_PATTERN.match(value):
            raise ValidationException(
                f"{field_name}只能包含英文、数字、下划线和连字符",
                {"field": field_name, "value": value}
            )

    @staticmethod
    def validate_enum_value(
        value: str,
        field_name: str,
        allowed_values: List[str]
    ) -> None:
        """验证枚举值"""
        if value not in allowed_values:
            raise ValidationException(
                f"{field_name}的值无效，允许的值: {', '.join(allowed_values)}",
                {"field": field_name, "value": value, "allowed_values": allowed_values}
            )

    @staticmethod
    def validate_boolean(value: Any, field_name: str) -> None:
        """验证布尔值"""
        if not isinstance(value, bool):
            raise ValidationException(
                f"{field_name}必须是布尔值",
                {"field": field_name, "value": value, "expected_type": "boolean"}
            )

    @staticmethod
    def validate_list(
        value: Any,
        field_name: str,
        min_length: int = 0,
        max_length: int = 1000
    ) -> None:
        """验证列表"""
        if not isinstance(value, list):
            raise ValidationException(
                f"{field_name}必须是列表",
                {"field": field_name, "value": value, "expected_type": "list"}
            )

        if len(value) < min_length:
            raise ValidationException(
                f"{field_name}至少需要{min_length}个元素",
                {"field": field_name, "value": value, "min_length": min_length}
            )

        if len(value) > max_length:
            raise ValidationException(
                f"{field_name}最多允许{max_length}个元素",
                {"field": field_name, "value": value, "max_length": max_length}
            )

    @staticmethod
    def validate_dict(value: Any, field_name: str) -> None:
        """验证字典"""
        if not isinstance(value, dict):
            raise ValidationException(
                f"{field_name}必须是对象",
                {"field": field_name, "value": value, "expected_type": "object"}
            )

    @staticmethod
    def sanitize_string(value: str) -> str:
        """清理字符串，移除潜在的危险字符"""
        if not isinstance(value, str):
            return value

        # 移除控制字符
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)

        # 限制长度
        if len(sanitized) > 10000:
            sanitized = sanitized[:10000]

        return sanitized.strip()

    @staticmethod
    def validate_json_size(data: Dict[str, Any], max_size_kb: int = 100) -> None:
        """验证JSON数据大小"""
        import json
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            size_kb = len(json_str.encode('utf-8')) / 1024

            if size_kb > max_size_kb:
                raise ValidationException(
                    f"请求数据过大，最大允许{max_size_kb}KB",
                    {"size_kb": size_kb, "max_size_kb": max_size_kb}
                )
        except (TypeError, ValueError) as e:
            raise ValidationException(
                "请求数据格式无效",
                {"error": str(e)}
            )


class SecurityValidator:
    """安全验证器"""

    # SQL注入检测模式
    SQL_INJECTION_PATTERNS = [
        re.compile(r'\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b', re.IGNORECASE),
        re.compile(r'[\'";].*[\'";]', re.IGNORECASE),
        re.compile(r'--.*$', re.MULTILINE),
        re.compile(r'/\*.*\*/', re.DOTALL),
    ]

    # XSS检测模式
    XSS_PATTERNS = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'<iframe[^>]*>', re.IGNORECASE),
    ]

    @staticmethod
    def check_sql_injection(value: str, field_name: str) -> None:
        """检查SQL注入"""
        if not isinstance(value, str):
            return

        for pattern in SecurityValidator.SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                raise ValidationException(
                    f"{field_name}包含可疑的SQL代码",
                    {"field": field_name, "security_issue": "sql_injection"}
                )

    @staticmethod
    def check_xss(value: str, field_name: str) -> None:
        """检查XSS攻击"""
        if not isinstance(value, str):
            return

        for pattern in SecurityValidator.XSS_PATTERNS:
            if pattern.search(value):
                raise ValidationException(
                    f"{field_name}包含可疑的脚本代码",
                    {"field": field_name, "security_issue": "xss"}
                )

    @staticmethod
    def validate_safe_string(value: str, field_name: str) -> None:
        """验证安全字符串"""
        SecurityValidator.check_sql_injection(value, field_name)
        SecurityValidator.check_xss(value, field_name)

    @staticmethod
    def validate_file_path(value: str, field_name: str) -> None:
        """验证文件路径安全性"""
        if not isinstance(value, str):
            raise ValidationException(
                f"{field_name}必须是字符串",
                {"field": field_name, "value": value}
            )

        # 检查路径遍历攻击
        if '..' in value or value.startswith('/') or '\\' in value:
            raise ValidationException(
                f"{field_name}包含非法路径字符",
                {"field": field_name, "value": value, "security_issue": "path_traversal"}
            )

        # 检查危险文件扩展名
        dangerous_extensions = ['.exe', '.bat', '.cmd', '.sh', '.ps1', '.vbs', '.js']
        for ext in dangerous_extensions:
            if value.lower().endswith(ext):
                raise ValidationException(
                    f"{field_name}包含危险的文件扩展名",
                    {"field": field_name, "value": value, "security_issue": "dangerous_extension"}
                )


def validate_request_data(data: Dict[str, Any], max_size_kb: int = 100) -> Dict[str, Any]:
    """验证请求数据"""
    # 验证数据大小
    InputValidator.validate_json_size(data, max_size_kb)

    # 清理字符串字段
    cleaned_data = {}
    for key, value in data.items():
        if isinstance(value, str):
            cleaned_data[key] = InputValidator.sanitize_string(value)
            SecurityValidator.validate_safe_string(cleaned_data[key], key)
        else:
            cleaned_data[key] = value

    return cleaned_data