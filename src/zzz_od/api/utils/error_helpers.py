"""
错误处理辅助函数

提供简化的错误抛出和处理工具
"""
from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from zzz_od.api.battle_assistant_models import (
    BattleAssistantError,
    ConfigurationError,
    TaskExecutionError,
    FileOperationError,
    GamepadError,
    ValidationError,
    TaskAlreadyRunningError,
    ConfigNotFoundError,
    TemplateNotFoundError,
    PermissionError
)

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


def handle_battle_assistant_errors(func: F) -> F:
    """
    装饰器：自动处理战斗助手相关错误
    将常见的异常转换为战斗助手异常
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BattleAssistantError:
            # 已经是战斗助手异常，直接抛出
            raise
        except FileNotFoundError as e:
            raise ConfigNotFoundError(f"文件未找到: {str(e)}")
        except PermissionError as e:
            raise PermissionError(f"权限不足: {str(e)}")
        except ValueError as e:
            raise ValidationError(f"参数验证失败: {str(e)}")
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
            raise BattleAssistantError(f"操作失败: {str(e)}")

    return wper


def raise_config_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """抛出配置错误"""
    raise ConfigurationError(message, details)


def raise_task_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """抛出任务执行错误"""
    raise TaskExecutionError(message, details)


def raise_file_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """抛出文件操作错误"""
    raise FileOperationError(message, details)


def raise_validation_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """抛出验证错误"""
    raise ValidationError(message, details)


def raise_gamepad_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """抛出手柄错误"""
    raise GamepadError(message, details)


def raise_task_running_error(message: str = "任务已在运行", details: Optional[Dict[str, Any]] = None) -> None:
    """抛出任务已运行错误"""
    raise TaskAlreadyRunningError(message, details)


def raise_config_not_found_error(config_name: str, config_type: str = "配置") -> None:
    """抛出配置未找到错误"""
    raise ConfigNotFoundError(f"{config_type} '{config_name}' 未找到")


def raise_template_not_found_error(template_name: str) -> None:
    """抛出模板未找到错误"""
    raise TemplateNotFoundError(f"模板 '{template_name}' 未找到")


def check_task_not_running(ctx, error_message: str = "已有任务正在运行，请先停止当前任务") -> None:
    """检查任务是否未在运行，如果在运行则抛出异常"""
    if ctx.is_context_running:
        raise_task_running_error(error_message)


def validate_config_name(config_name: str, config_type: str = "配置") -> None:
    """验证配置名称"""
    if not config_name or not config_name.strip():
        raise_validation_error(f"{config_type}名称不能为空")

    if len(config_name) > 100:
        raise_validation_error(f"{config_type}名称过长，最大长度为100字符")

    # 检查非法字符
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        if char in config_name:
            raise_validation_error(f"{config_type}名称包含非法字符: {char}")


def validate_numeric_range(
    value: Union[int, float],
    min_val: Union[int, float],
    max_val: Union[int, float],
    field_name: str
) -> None:
    """验证数值范围"""
    if value < min_val:
        raise_validation_error(f"{field_name}不能小于{min_val}")
    if value > max_val:
        raise_validation_error(f"{field_name}不能大于{max_val}")


def create_error_details(operation: str, resource: str, **kwargs) -> Dict[str, Any]:
    """创建错误详情字典"""
    details = {
        "operation": operation,
        "resource": resource,
    }
    details.update(kwargs)
    return details


def log_and_raise_error(
    error_class: type,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    log_level: str = "error"
) -> None:
    """记录日志并抛出错误"""
    log_message = f"{error_class.__name__}: {message}"
    if details:
        log_message += f" Details: {details}"

    if log_level == "error":
        logger.error(log_message)
    elif log_level == "warning":
        logger.warning(log_message)
    elif log_level == "info":
        logger.info(log_message)

    raise error_class(message, details)


class ErrorContext:
    """错误上下文管理器"""

    def __init__(self, operation: str, resource: str):
        self.operation = operation
        self.resource = resource
        self.details = {}

    def add_detail(self, key: str, value: Any) -> 'ErrorContext':
        """添加错误详情"""
        self.details[key] = value
        return self

    def raise_config_error(self, message: str) -> None:
        """抛出配置错误"""
        details = create_error_details(self.operation, self.resource, **self.details)
        raise ConfigurationError(message, details)

    def raise_task_error(self, message: str) -> None:
        """抛出任务错误"""
        details = create_error_details(self.operation, self.resource, **self.details)
        raise TaskExecutionError(message, details)

    def raise_file_error(self, message: str) -> None:
        """抛出文件错误"""
        details = create_error_details(self.operation, self.resource, **self.details)
        raise FileOperationError(message, details)


def error_context(operation: str, resource: str) -> ErrorContext:
    """创建错误上下文"""
    return ErrorContext(operation, resource)


# 常用的错误检查函数
def ensure_file_exists(file_path: str, file_type: str = "文件") -> None:
    """确保文件存在"""
    import os
    if not os.path.exists(file_path):
        if file_type == "配置":
            raise_config_not_found_error(file_path, file_type)
        elif file_type == "模板":
            raise_template_not_found_error(file_path)
        else:
            raise_file_error(f"{file_type}不存在: {file_path}")


def ensure_directory_writable(directory_path: str) -> None:
    """确保目录可写"""
    import os
    if not os.access(directory_path, os.W_OK):
        raise PermissionError(f"目录不可写: {directory_path}")


def ensure_config_not_current(config_name: str, current_config: str, config_type: str = "配置") -> None:
    """确保配置不是当前使用的配置"""
    if config_name == current_config:
        raise_validation_error(f"不能删除当前正在使用的{config_type}: {config_name}")


def ensure_not_sample_config(config_name: str, sample_configs: list, config_type: str = "配置") -> None:
    """确保不是示例配置"""
    if config_name in sample_configs:
        raise_validation_error(f"不能删除示例{config_type}: {config_name}")