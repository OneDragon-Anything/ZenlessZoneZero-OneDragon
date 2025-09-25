"""
统一安全工具模块

提供常用的安全工具函数和装饰器
"""
from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import Request

from .unified_errors import AuthorizationException, ValidationException
from .unified_validation import InputValidator, SecurityValidator

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


def require_auth(func: F) -> F:
    """要求认证的装饰器"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # 检查是否有认证信息
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break

        if request and not hasattr(request.state, 'authenticated'):
            raise AuthorizationException("需要认证")

        return await func(*args, **kwargs)

    return wrapper


def validate_input(**validators) -> Callable[[F], F]:
    """输入验证装饰器"""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 验证参数
            for param_name, validator_func in validators.items():
                if param_name in kwargs:
                    try:
                        validator_func(kwargs[param_name], param_name)
                    except Exception as e:
                        logger.warning(f"参数验证失败: {param_name} - {str(e)}")
                        raise

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def sanitize_response(func: F) -> F:
    """响应清理装饰器"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)

        # 如果返回的是字典，清理敏感信息
        if isinstance(result, dict):
            return _sanitize_dict(result)

        return result

    return wrapper


def _sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """清理字典中的敏感信息"""
    sensitive_keys = ['password', 'token', 'secret', 'key', 'api_key']

    sanitized = {}
    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = "***"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = [_sanitize_dict(item) if isinstance(item, dict) else item for item in value]
        else:
            sanitized[key] = value

    return sanitized


def log_security_event(event_type: str, details: Dict[str, Any], request: Optional[Request] = None) -> None:
    """记录安全事件"""
    log_data = {
        "event_type": event_type,
        "details": details,
        "timestamp": None  # 将由日志系统添加
    }

    if request:
        log_data.update({
            "client_ip": getattr(request.client, 'host', 'unknown') if request.client else 'unknown',
            "user_agent": request.headers.get("user-agent", "unknown"),
            "path": str(request.url.path),
            "method": request.method
        })

    logger.warning(f"安全事件: {event_type}", extra=log_data)


class SecurityContext:
    """安全上下文管理器"""

    def __init__(self, request: Request):
        self.request = request
        self.client_ip = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
        self.user_agent = request.headers.get("user-agent", "unknown")

    def validate_config_name(self, config_name: str) -> None:
        """验证配置名称"""
        try:
            InputValidator.validate_config_name(config_name)
            SecurityValidator.validate_safe_string(config_name, "配置名称")
        except ValidationException as e:
            log_security_event("invalid_config_name", {
                "config_name": config_name,
                "error": str(e)
            }, self.request)
            raise

    def validate_module_name(self, module_name: str) -> None:
        """验证模块名称"""
        try:
            InputValidator.validate_module_name(module_name)
            SecurityValidator.validate_safe_string(module_name, "模块名称")
        except ValidationException as e:
            log_security_event("invalid_module_name", {
                "module_name": module_name,
                "error": str(e)
            }, self.request)
            raise

    def validate_file_path(self, file_path: str) -> None:
        """验证文件路径"""
        try:
            SecurityValidator.validate_file_path(file_path, "文件路径")
        except ValidationException as e:
            log_security_event("invalid_file_path", {
                "file_path": file_path,
                "error": str(e)
            }, self.request)
            raise

    def check_rate_limit(self, identifier: str, max_requests: int = 100, window_seconds: int = 60) -> None:
        """检查速率限制"""
        # 这里可以集成更复杂的速率限制逻辑
        pass


def create_security_context(request: Request) -> SecurityContext:
    """创建安全上下文"""
    return SecurityContext(request)


# 常用验证器
def validate_uuid_param(value: str, field_name: str) -> None:
    """UUID参数验证器"""
    InputValidator.validate_uuid(value, field_name)


def validate_config_name_param(value: str, field_name: str) -> None:
    """配置名称参数验证器"""
    InputValidator.validate_config_name(value, field_name)
    SecurityValidator.validate_safe_string(value, field_name)


def validate_module_name_param(value: str, field_name: str) -> None:
    """模块名称参数验证器"""
    InputValidator.validate_module_name(value, field_name)
    SecurityValidator.validate_safe_string(value, field_name)


def validate_numeric_param(value: float, field_name: str, min_val: float = 0, max_val: float = 100) -> None:
    """数值参数验证器"""
    InputValidator.validate_numeric_range(value, field_name, min_val, max_val)


def validate_boolean_param(value: bool, field_name: str) -> None:
    """布尔参数验证器"""
    InputValidator.validate_boolean(value, field_name)