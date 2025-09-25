"""
战斗助手异常处理中间件

提供统一的异常处理和错误响应格式化
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

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
    AccessDeniedError,
    ErrorResponse,
    ErrorDetail
)

logger = logging.getLogger(__name__)


def _get_status_code_for_error(error: BattleAssistantError) -> int:
    """根据错误类型获取HTTP状态码"""
    status_code_map = {
        "CONFIGURATION_ERROR": 400,
        "VALIDATION_ERROR": 400,
        "TASK_ALREADY_RUNNING": 409,
        "CONFIG_NOT_FOUND": 404,
        "TEMPLATE_NOT_FOUND": 404,
        "PERMISSION_ERROR": 403,
        "FILE_OPERATION_ERROR": 500,
        "TASK_EXECUTION_ERROR": 500,
        "GAMEPAD_ERROR": 400,
        "BATTLE_ASSISTANT_ERROR": 500
    }
    return status_code_map.get(error.code, 500)


class BattleAssistantExceptionHandler(BaseHTTPMiddleware):
    """战斗助手异常处理中间件"""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            return await self.handle_exception(request, exc)

    async def handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """处理异常并返回标准化错误响应"""

        # 记录异常信息
        logger.exception(f"Exception in {request.method} {request.url}: {str(exc)}")

        # 处理战斗助手自定义异常
        if isinstance(exc, BattleAssistantError):
            return self._create_error_response(
                status_code=self._get_status_code_for_error(exc),
                error_code=exc.code,
                message=exc.message,
                details=exc.details
            )

        # 处理HTTP异常
        elif isinstance(exc, HTTPException):
            return self._create_error_response(
                status_code=exc.status_code,
                error_code="HTTP_ERROR",
                message=str(exc.detail) if isinstance(exc.detail, str) else "HTTP错误",
                details=exc.detail if not isinstance(exc.detail, str) else None
            )

        # 处理其他异常
        else:
            return self._create_error_response(
                status_code=500,
                error_code="INTERNAL_SERVER_ERROR",
                message="服务器内部错误",
                details={"exception_type": type(exc).__name__, "exception_message": str(exc)}
            )

    def _get_status_code_for_error(self, error: BattleAssistantError) -> int:
        """根据错误类型获取HTTP状态码"""
        return _get_status_code_for_error(error)

    def _create_error_response(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Dict[str, Any] = None
    ) -> JSONResponse:
        """创建标准化错误响应"""
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=error_code,
                message=message,
                details=details
            )
        )

        return JSONResponse(
            status_code=status_code,
            content=error_response.model_dump()
        )


def create_battle_assistant_exception_handlers():
    """创建战斗助手异常处理器字典"""

    async def handle_battle_assistant_error(request: Request, exc: BattleAssistantError):
        """处理战斗助手基础异常"""
        logger.exception(f"BattleAssistantError in {request.method} {request.url}: {exc.message}")

        status_code = _get_status_code_for_error(exc)

        error_response = ErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                details=exc.details
            )
        )

        return JSONResponse(
            status_code=status_code,
            content=error_response.model_dump()
        )

    async def handle_configuration_error(request: Request, exc: ConfigurationError):
        """处理配置错误"""
        return await handle_battle_assistant_error(request, exc)

    async def handle_task_execution_error(request: Request, exc: TaskExecutionError):
        """处理任务执行错误"""
        return await handle_battle_assistant_error(request, exc)

    async def handle_file_operation_error(request: Request, exc: FileOperationError):
        """处理文件操作错误"""
        return await handle_battle_assistant_error(request, exc)

    async def handle_gamepad_error(request: Request, exc: GamepadError):
        """处理手柄错误"""
        return await handle_battle_assistant_error(request, exc)

    async def handle_validation_error(request: Request, exc: ValidationError):
        """处理验证错误"""
        return await handle_battle_assistant_error(request, exc)

    async def handle_task_already_running_error(request: Request, exc: TaskAlreadyRunningError):
        """处理任务已运行错误"""
        return await handle_battle_assistant_error(request, exc)

    async def handle_config_not_found_error(request: Request, exc: ConfigNotFoundError):
        """处理配置未找到错误"""
        return await handle_battle_assistant_error(request, exc)

    async def handle_template_not_found_error(request: Request, exc: TemplateNotFoundError):
        """处理模板未找到错误"""
        return await handle_battle_assistant_error(request, exc)

    async def handle_access_denied_error(request: Request, exc: AccessDeniedError):
        """处理权限错误"""
        return await handle_battle_assistant_error(request, exc)

    return {
        BattleAssistantError: handle_battle_assistant_error,
        ConfigurationError: handle_configuration_error,
        TaskExecutionError: handle_task_execution_error,
        FileOperationError: handle_file_operation_error,
        GamepadError: handle_gamepad_error,
        ValidationError: handle_validation_error,
        TaskAlreadyRunningError: handle_task_already_running_error,
        ConfigNotFoundError: handle_config_not_found_error,
        TemplateNotFoundError: handle_template_not_found_error,
        AccessDeniedError: handle_access_denied_error,
    }