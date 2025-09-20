"""
统一异常处理器

提供全局异常处理，确保HTTP状态码的一致性和标准化错误响应
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError,tion
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .unified_errors import (
    UnifiedAPIException,
    ErrorResponse,
    ErrorDetail,
    APIErrorCode,
    InternalServerException
)
from .battle_assistant_models import BattleAssistantError
from .security import create_secure_headers

logger = logging.getLogger(__name__)


async def unified_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """统一异常处理器"""

    # 添加安全响应头
    headers = create_secure_headers()

    # 处理统一API异常
    if isinstance(exc, UnifiedAPIException):
        logger.warning(f"API异常: {exc.error_code} - {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
            headers=headers
        )

    # 处理FastAPI的HTTP异常
    if isinstance(exc, HTTPException):
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=_map_http_status_to_error_code(exc.status_code),
                message=str(exc.detail),
                details={"status_code": exc.status_code}
            )
        )
        logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers=headers
        )

    # 处理Pydantic验证错误
    if isinstance(exc, (RequestValidationError, ValidationError)):
        error_details = []
        for error in exc.errors():
            error_details.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })

        error_response = ErrorResponse(
            error=ErrorDetail(
                code=APIErrorCode.VALIDATION_ERROR,
                message="请求参数验证失败",
                details={"validation_errors": error_details}
            )
        )
        logger.warning(f"验证错误: {error_details}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response.model_dump(),
            headers=headers
        )

    # 处理战斗助手异常
    if isinstance(exc, BattleAssistantError):
        error_code = _map_battle_assistant_error_to_api_code(exc)
        status_code = _get_status_code_for_error(error_code)

        error_response = ErrorResponse(
            error=ErrorDetail(
                code=error_code,
                message=exc.message,
                details=exc.details
            )
        )
        logger.warning(f"战斗助手异常: {exc.code} - {exc.message}")
        return JSONResponse(
            status_code=status_code,
            content=error_response.model_dump(),
            headers=headers
        )

    # 处理其他未知异常
    logger.exception(f"未处理的异常: {type(exc).__name__} - {str(exc)}")

    error_response = ErrorResponse(
        error=ErrorDetail(
            code=APIErrorCode.INTERNAL_SERVER_ERROR,
            message="内部服务器错误",
            details={"exception_type": type(exc).__name__}
        )
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
        headers=headers
    )


def _map_http_status_to_error_code(status_code: int) -> APIErrorCode:
    """将HTTP状态码映射到错误码"""
    mapping = {
        400: APIErrorCode.INVALID_REQUEST,
        401: APIErrorCode.AUTHENTICATION_FAILED,
        403: APIErrorCode.AUTHORIZATION_FAILED,
        404: APIErrorCode.RESOURCE_NOT_FOUND,
        405: APIErrorCode.OPERATION_NOT_SUPPORTED,
        409: APIErrorCode.TASK_ALREADY_RUNNING,
        429: APIErrorCode.RATE_LIMIT_EXCEEDED,
        500: APIErrorCode.INTERNAL_SERVER_ERROR,
    }
    return mapping.get(status_code, APIErrorCode.INTERNAL_SERVER_ERROR)


def _map_battle_assistant_error_to_api_code(exc: BattleAssistantError) -> APIErrorCode:
    """将战斗助手异常映射到API错误码"""
    mapping = {
        "CONFIGURATION_ERROR": APIErrorCode.CONFIGURATION_ERROR,
        "TASK_EXECUTION_ERROR": APIErrorCode.TASK_START_FAILED,
        "FILE_OPERATION_ERROR": APIErrorCode.FILE_OPERATION_ERROR,
        "GAMEPAD_ERROR": APIErrorCode.GAMEPAD_ERROR,
        "VALIDATION_ERROR": APIErrorCode.VALIDATION_ERROR,
        "TASK_ALREADY_RUNNING": APIErrorCode.TASK_ALREADY_RUNNING,
        "CONFIG_NOT_FOUND": APIErrorCode.CONFIG_NOT_FOUND,
        "TEMPLATE_NOT_FOUND": APIErrorCode.TEMPLATE_NOT_FOUND,
        "PERMISSION_ERROR": APIErrorCode.FILE_ACCESS_DENIED,
    }
    return mapping.get(exc.code, APIErrorCode.INTERNAL_SERVER_ERROR)


def _get_status_code_for_error(error_code: APIErrorCode) -> int:
    """获取错误码对应的HTTP状态码"""
    mapping = {
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
        APIErrorCode.FILE_ACCESS_DENIED: status.HTTP_403_FORBIDDEN,
    }
    return mapping.get(error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


def setup_exception_handlers(app) -> None:
    """设置异常处理器"""

    # 添加统一异常处理器
    app.add_exception_handler(Exception, unified_exception_handler)

    # 添加特定异常处理器
    app.add_exception_handler(UnifiedAPIException, unified_exception_handler)
    app.add_exception_handler(HTTPException, unified_exception_handler)
    app.add_exception_handler(RequestValidationError, unified_exception_handler)
    app.add_exception_handler(ValidationError, unified_exception_handler)
    app.add_exception_handler(BattleAssistantError, unified_exception_handler)

    logger.info("统一异常处理器已设置")