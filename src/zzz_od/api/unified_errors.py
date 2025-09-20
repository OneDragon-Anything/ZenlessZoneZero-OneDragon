"""
统一API错误处理模块

提供标准化的错误响应格式、错误码定义和HTTP状态码处理
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from pydantic import BaseModel


class APIErrorCode(str, Enum):
    """API错误码枚举"""
    # 通用错误
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # 任务控制错误
    TASK_START_FAILED = "TASK_START_FAILED"
    TASK_STOP_FAILED = "TASK_STOP_FAILED"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_ALREADY_RUNNING = "TASK_ALREADY_RUNNING"
    OPERATION_NOT_SUPPORTED = "OPERATION_NOT_SUPPORTED"

    # 配置错误
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    CONFIG_VALIDATION_FAILED = "CONFIG_VALIDATION_FAILED"

    # 文件操作错误
    FILE_OPERATION_ERROR = "FILE_OPERATION_ERROR"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_ACCESS_DENIED = "FILE_ACCESS_DENIED"

    # WebSocket错误
    WEBSOCKET_CONNECTION_FAILED = "WEBSOCKET_CONNECTION_FAILED"
    MESSAGE_TOO_LARGE = "MESSAGE_TOO_LARGE"

    # 游戏相关错误
    GAMEPAD_ERROR = "GAMEPAD_ERROR"
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"


class ErrorDetail(BaseModel):
    """错误详情模型"""
    code: APIErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """标准错误响应模型"""
    ok: bool = False
    error: ErrorDetail


class UnifiedAPIException(HTTPException):
    """统一API异常基类"""

    def __init__(
        self,
        status_code: int,
        error_code: APIErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.error_details = details

        error_response = ErrorResponse(
            error=ErrorDetail(
                code=error_code,
                message=message,
                details=details
            )
        )

        super().__init__(
            status_code=status_code,
            detail=error_response.model_dump()
        )


# 具体异常类定义
class ValidationException(UnifiedAPIException):
    """输入验证异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=APIErrorCode.VALIDATION_ERROR,
            message=message,
            details=details
        )


class AuthenticationException(UnifiedAPIException):
    """认证异常"""
    def __init__(self, message: str = "认证失败", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=APIErrorCode.AUTHENTICATION_FAILED,
            message=message,
            details=details
        )


class AuthorizationException(UnifiedAPIException):
    """授权异常"""
    def __init__(self, message: str = "权限不足", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=APIErrorCode.AUTHORIZATION_FAILED,
            message=message,
            details=details
        )


class ResourceNotFoundException(UnifiedAPIException):
    """资源未找到异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=APIErrorCode.RESOURCE_NOT_FOUND,
            message=message,
            details=details
        )


class TaskAlreadyRunningException(UnifiedAPIException):
    """任务已运行异常"""
    def __init__(self, message: str = "任务已在运行", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code=APIErrorCode.TASK_ALREADY_RUNNING,
            message=message,
            details=details
        )


class OperationNotSupportedException(UnifiedAPIException):
    """操作不支持异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            error_code=APIErrorCode.OPERATION_NOT_SUPPORTED,
            message=message,
            details=details
        )


class RateLimitExceededException(UnifiedAPIException):
    """限流异常"""
    def __init__(self, message: str = "请求频率过高", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code=APIErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            details=details
        )


class InternalServerException(UnifiedAPIException):
    """内部服务器异常"""
    def __init__(self, message: str = "内部服务器错误", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=APIErrorCode.INTERNAL_SERVER_ERROR,
            message=message,
            details=details
        )


# 错误码到HTTP状态码的映射
ERROR_CODE_TO_STATUS = {
    APIErrorCode.VALIDATION_ERROR: status.HTTP_400_BAD_REQUEST,
    APIErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    APIErrorCode.AUTHENTICATION_FAILED: status.HTTP_401_UNAUTHORIZED,
    APIErrorCode.AUTHORIZATION_FAILED: status.HTTP_403_FORBIDDEN,
    APIErrorCode.RESOURCE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    APIErrorCode.TASK_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    APIErrorCode.CONFIG_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    APIErrorCode.FILE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    APIErrorCode.TEMPLATE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    APIErrorCode.OPERATION_NOT_SUPPORTED: status.HTTP_405_METHOD_NOT_ALLOWED,
    APIErrorCode.TASK_ALREADY_RUNNING: status.HTTP_409_CONFLICT,
    APIErrorCode.RATE_LIMIT_EXCEEDED: status.HTTP_429_TOO_MANY_REQUESTS,
    APIErrorCode.INTERNAL_SERVER_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    APIErrorCode.TASK_START_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
    APIErrorCode.TASK_STOP_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
    APIErrorCode.CONFIGURATION_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    APIErrorCode.FILE_OPERATION_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    APIErrorCode.WEBSOCKET_CONNECTION_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
    APIErrorCode.GAMEPAD_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def create_unified_exception(
    error_code: APIErrorCode,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> UnifiedAPIException:
    """创建统一异常"""
    status_code = ERROR_CODE_TO_STATUS.get(error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    return UnifiedAPIException(status_code, error_code, message, details)


def raise_unified_error(
    error_code: APIErrorCode,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """抛出统一错误"""
    raise create_unified_exception(error_code, message, details)