"""
数据清理和验证工具
"""
import re
import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime


logger = logging.getLogger(__name__)


class DataSanitizer:
    """数据清理器"""

    # 最大字符串长度
    MAX_STRING_LENGTH = 1000

    # 最大堆栈跟踪长度
    MAX_STACK_TRACE_LENGTH = 5000

    # 最大属性数量
    MAX_PROPERTIES_COUNT = 50

    # 最大嵌套深度
    MAX_NESTING_DEPTH = 5

    # 文件路径模式（用于清理路径信息）
    FILE_PATH_PATTERNS = [
        re.compile(r'[A-Za-z]:\\[^\\]+\\.*'),  # Windows路径
        re.compile(r'/[^/]+/.*'),              # Unix路径
        re.compile(r'file:///.*'),             # 文件URL
    ]

    # 系统信息模式
    SYSTEM_INFO_PATTERNS = [
        re.compile(r'Computer Name: [^\n]+'),
        re.compile(r'User Name: [^\n]+'),
        re.compile(r'Domain: [^\n]+'),
    ]

    def __init__(self):
        self.sanitization_stats = {
            'strings_truncated': 0,
            'properties_removed': 0,
            'paths_sanitized': 0,
            'system_info_removed': 0
        }

    def sanitize_error_data(self, error_data: Dict[str, Any]) -> Dict[str, Any]:
        """清理错误数据"""
        try:
            sanitized = {}

            for key, value in error_data.items():
                if key == 'stack_trace':
                    sanitized[key] = self._sanitize_stack_trace(value)
                elif key == 'error_message':
                    sanitized[key] = self._sanitize_error_message(value)
                elif key == 'context':
                    sanitized[key] = self._sanitize_context(value)
                elif key == 'system_info':
                    sanitized[key] = self._sanitize_system_info(value)
                else:
                    sanitized[key] = self._sanitize_value(value)

            return sanitized

        except Exception as e:
            logger.error(f"Failed to sanitize error data: {e}")
            return error_data

    def sanitize_event_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """清理事件属性"""
        try:
            return self._sanitize_dict(properties, depth=0)
        except Exception as e:
            logger.error(f"Failed to sanitize event properties: {e}")
            return properties

    def _sanitize_dict(self, data: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
        """清理字典数据"""
        if depth > self.MAX_NESTING_DEPTH:
            return {"[TRUNCATED]": "Max nesting depth exceeded"}

        if len(data) > self.MAX_PROPERTIES_COUNT:
            # 保留前N个属性
            items = list(data.items())[:self.MAX_PROPERTIES_COUNT]
            sanitized = dict(items)
            sanitized["[TRUNCATED]"] = f"Removed {len(data) - self.MAX_PROPERTIES_COUNT} properties"
            self.sanitization_stats['properties_removed'] += len(data) - self.MAX_PROPERTIES_COUNT
        else:
            sanitized = {}
            for key, value in data.items():
                sanitized[key] = self._sanitize_value(value, depth + 1)

        return sanitized

    def _sanitize_value(self, value: Any, depth: int = 0) -> Any:
        """清理单个值"""
        if isinstance(value, str):
            return self._sanitize_string(value)
        elif isinstance(value, dict):
            return self._sanitize_dict(value, depth)
        elif isinstance(value, list):
            return self._sanitize_list(value, depth)
        elif isinstance(value, (int, float, bool)):
            return value
        elif value is None:
            return None
        else:
            # 其他类型转换为字符串并清理
            return self._sanitize_string(str(value))

    def _sanitize_list(self, items: List[Any], depth: int = 0) -> List[Any]:
        """清理列表数据"""
        if depth > self.MAX_NESTING_DEPTH:
            return ["[TRUNCATED: Max nesting depth exceeded]"]

        # 限制列表长度
        max_items = 20
        if len(items) > max_items:
            sanitized = [self._sanitize_value(item, depth + 1) for item in items[:max_items]]
            sanitized.append(f"[TRUNCATED: {len(items) - max_items} more items]")
        else:
            sanitized = [self._sanitize_value(item, depth + 1) for item in items]

        return sanitized

    def _sanitize_string(self, text: str) -> str:
        """清理字符串"""
        if not isinstance(text, str):
            text = str(text)

        # 截断过长的字符串
        if len(text) > self.MAX_STRING_LENGTH:
            text = text[:self.MAX_STRING_LENGTH] + "[TRUNCATED]"
            self.sanitization_stats['strings_truncated'] += 1

        # 清理文件路径
        text = self._sanitize_file_paths(text)

        # 清理系统信息
        text = self._sanitize_system_info_in_text(text)

        return text

    def _sanitize_stack_trace(self, stack_trace: str) -> str:
        """清理堆栈跟踪"""
        if not isinstance(stack_trace, str):
            stack_trace = str(stack_trace)

        # 截断过长的堆栈跟踪
        if len(stack_trace) > self.MAX_STACK_TRACE_LENGTH:
            lines = stack_trace.split('\n')
            # 保留前面和后面的部分
            keep_lines = self.MAX_STACK_TRACE_LENGTH // 100  # 大约50行
            if len(lines) > keep_lines * 2:
                truncated_lines = (
                    lines[:keep_lines] +
                    [f"[TRUNCATED: {len(lines) - keep_lines * 2} lines removed]"] +
                    lines[-keep_lines:]
                )
                stack_trace = '\n'.join(truncated_lines)

        # 清理文件路径
        stack_trace = self._sanitize_file_paths(stack_trace)

        return stack_trace

    def _sanitize_error_message(self, message: str) -> str:
        """清理错误消息"""
        if not isinstance(message, str):
            message = str(message)

        # 清理文件路径
        message = self._sanitize_file_paths(message)

        # 截断过长的消息
        if len(message) > 500:
            message = message[:500] + "[TRUNCATED]"

        return message

    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """清理上下文信息"""
        if not isinstance(context, dict):
            return {"sanitized_context": str(context)}

        return self._sanitize_dict(context)

    def _sanitize_system_info(self, system_info: Dict[str, Any]) -> Dict[str, Any]:
        """清理系统信息"""
        if not isinstance(system_info, dict):
            return {"sanitized_system_info": str(system_info)}

        sanitized = {}

        # 允许的系统信息字段
        allowed_fields = {
            'platform', 'platform_version', 'python_version',
            'cpu_count', 'memory_total', 'architecture'
        }

        for key, value in system_info.items():
            if key.lower() in allowed_fields:
                sanitized[key] = self._sanitize_value(value)
            else:
                # 敏感的系统信息用通用值替换
                if 'name' in key.lower() or 'user' in key.lower():
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = self._sanitize_value(value)

        return sanitized

    def _sanitize_file_paths(self, text: str) -> str:
        """清理文件路径"""
        sanitized = text

        for pattern in self.FILE_PATH_PATTERNS:
            matches = pattern.findall(sanitized)
            for match in matches:
                # 只保留文件名，移除完整路径
                if '\\' in match:
                    filename = match.split('\\')[-1]
                elif '/' in match:
                    filename = match.split('/')[-1]
                else:
                    filename = "[PATH]"

                sanitized = sanitized.replace(match, f"[PATH]/{filename}")
                self.sanitization_stats['paths_sanitized'] += 1

        return sanitized

    def _sanitize_system_info_in_text(self, text: str) -> str:
        """清理文本中的系统信息"""
        sanitized = text

        for pattern in self.SYSTEM_INFO_PATTERNS:
            sanitized = pattern.sub('[SYSTEM_INFO_REDACTED]', sanitized)
            if pattern.search(text):
                self.sanitization_stats['system_info_removed'] += 1

        return sanitized

    def validate_event_data(self, event_name: str, properties: Dict[str, Any]) -> bool:
        """验证事件数据"""
        try:
            # 检查事件名称
            if not event_name or not isinstance(event_name, str):
                return False

            if len(event_name) > 100:
                return False

            # 检查属性
            if not isinstance(properties, dict):
                return False

            if len(properties) > self.MAX_PROPERTIES_COUNT:
                return False

            # 检查属性值
            return self._validate_dict(properties)

        except Exception as e:
            logger.error(f"Failed to validate event data: {e}")
            return False

    def _validate_dict(self, data: Dict[str, Any], depth: int = 0) -> bool:
        """验证字典数据"""
        if depth > self.MAX_NESTING_DEPTH:
            return False

        for key, value in data.items():
            # 检查键
            if not isinstance(key, str) or len(key) > 100:
                return False

            # 检查值
            if not self._validate_value(value, depth + 1):
                return False

        return True

    def _validate_value(self, value: Any, depth: int = 0) -> bool:
        """验证单个值"""
        if isinstance(value, str):
            return len(value) <= self.MAX_STRING_LENGTH * 2  # 验证时允许更长
        elif isinstance(value, dict):
            return self._validate_dict(value, depth)
        elif isinstance(value, list):
            return len(value) <= 50 and all(self._validate_value(item, depth + 1) for item in value)
        elif isinstance(value, (int, float, bool)) or value is None:
            return True
        else:
            # 其他类型检查字符串长度
            return len(str(value)) <= self.MAX_STRING_LENGTH

    def get_sanitization_stats(self) -> Dict[str, int]:
        """获取清理统计信息"""
        return self.sanitization_stats.copy()

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.sanitization_stats = {
            'strings_truncated': 0,
            'properties_removed': 0,
            'paths_sanitized': 0,
            'system_info_removed': 0
        }