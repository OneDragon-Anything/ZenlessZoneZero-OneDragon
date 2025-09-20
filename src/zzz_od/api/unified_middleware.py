"""
统一API中间件

提供请求验证、安全检查和响应处理的中间件
"""
from __future__ import annotations

import json
import time
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .unified_validation import validate_request_data
from .unified_errors import ValidationException, RateLimitExceededException
from .security import create_secure_headers, get_client_ip

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """安全中间件"""

    def __init__(self, app, max_request_size_mb: int = 10):
        super().__init__(app)
        self.max_request_size_bytes = max_request_size_mb * 1024 * 1024

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        client_ip = get_client_ip(request)

        try:
            # 记录请求开始
            logger.info(f"请求开始: {request.method} {request.url.path} - IP: {client_ip}")

            # 检查请求大小
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_request_size_bytes:
                raise ValidationException(
                    f"请求体过大，最大允许{self.max_request_size_bytes // (1024*1024)}MB",
                    {"content_length": content_length, "max_size": self.max_request_size_bytes}
                )

            # 验证Content-Type（对于POST/PUT请求）
            if request.method in ["POST", "PUT", "PATCH"]:
                content_type = request.headers.get("content-type", "")
                if content_type and not content_type.startswith(("application/json", "multipart/form-data")):
                    logger.warning(f"不支持的Content-Type: {content_type}")

            # 处理请求
            response = await call_next(request)

            # 添加安全响应头
            security_headers = create_secure_headers()
            for key, value in security_headers.items():
                response.headers[key] = value

            # 记录请求完成
            process_time = time.time() - start_time
            logger.info(f"请求完成: {request.method} {request.url.path} - "
                       f"状态码: {response.status_code} - 耗时: {process_time:.3f}s")

            return response

        except Exception as e:
            # 记录异常
            process_time = time.time() - start_time
            logger.error(f"请求异常: {request.method} {request.url.path} - "
                        f"错误: {str(e)} - 耗时: {process_time:.3f}s")
            raise


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """请求验证中间件"""

    def __init__(self, app, validate_json: bool = True, max_json_size_kb: int = 100):
        super().__init__(app)
        self.validate_json = validate_json
        self.max_json_size_kb = max_json_size_kb

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 只对JSON请求进行验证
        if (self.validate_json and
            request.method in ["POST", "PUT", "PATCH"] and
            request.headers.get("content-type", "").startswith("application/json")):

            try:
                # 读取请求体
                body = await request.body()
                if body:
                    # 解析JSON
                    try:
                        json_data = json.loads(body)
                        if isinstance(json_data, dict):
                            # 验证请求数据
                            validated_data = validate_request_data(json_data, self.max_json_size_kb)

                            # 重新设置请求体（如果数据被清理过）
                            if validated_data != json_data:
                                new_body = json.dumps(validated_data, ensure_ascii=False).encode('utf-8')
                                request._body = new_body

                    except json.JSONDecodeError as e:
                        raise ValidationException(
                            "请求体JSON格式无效",
                            {"error": str(e)}
                        )

            except ValidationException:
                raise
            except Exception as e:
                logger.error(f"请求验证中间件异常: {str(e)}")
                raise ValidationException(
                    "请求验证失败",
                    {"error": str(e)}
                )

        return await call_next(request)


class ResponseMiddleware(BaseHTTPMiddleware):
    """响应处理中间件"""

    def __init__(self, app, add_request_id: bool = True):
        super().__init__(app)
        self.add_request_id = add_request_id

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成请求ID
        request_id = f"{int(time.time() * 1000)}-{hash(str(request.url)) % 10000:04d}"

        # 将请求ID添加到请求状态中
        if self.add_request_id:
            request.state.request_id = request_id

        response = await call_next(request)

        # 添加请求ID到响应头
        if self.add_request_id:
            response.headers["X-Request-ID"] = request_id

        # 添加API版本信息
        response.headers["X-API-Version"] = "v1"

        return response


def setup_middleware(app) -> None:
    """设置中间件"""

    # 添加响应中间件（最外层）
    app.add_middleware(ResponseMiddleware)

    # 添加安全中间件
    app.add_middleware(SecurityMiddleware, max_request_size_mb=10)

    # 添加请求验证中间件（最内层）
    app.add_middleware(RequestValidationMiddleware, validate_json=True, max_json_size_kb=100)

    logger.info("统一中间件已设置")