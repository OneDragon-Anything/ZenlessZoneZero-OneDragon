from __future__ import annotations

import os
import time
from typing import Optional, Dict
from collections import defaultdict

from fastapi import Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .unified_errors import AuthenticationException, RateLimitExceededException


class RateLimiter:
    """简单的速率限制器"""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, identifier: str) -> bool:
        """检查是否允许请求"""
        now = time.time()
        window_start = now - self.window_seconds

        # 清理过期的请求记录
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > window_start
        ]

        # 检查是否超过限制
        if len(self.requests[identifier]) >= self.max_requests:
            return False

        # 记录当前请求
        self.requests[identifier].append(now)
        return True


# 全局速率限制器
_rate_limiter = RateLimiter()


def get_api_key_dependency():
    """
    返回一个依赖函数：当设置环境变量 OD_API_KEY 时，要求请求头携带 `X-Api-Key` 且匹配；
    未设置时，不进行鉴权。
    用法：dependencies=[Depends(get_api_key_dependency())]
    """

    expected = os.getenv("OD_API_KEY")
    if not expected:
        async def _noop(
            request: Request,
            x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key")
        ) -> None:  # noqa: ARG001
            # 即使不需要认证，也进行速率限制
            client_ip = get_client_ip(request)
            if not _rate_limiter.is_allowed(client_ip):
                raise RateLimitExceededException("请求频率过高，请稍后再试")
            return None

        return _noop

    async def _require(
        request: Request,
        x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key")
    ) -> None:
        # 速率限制检查
        client_ip = get_client_ip(request)
        if not _rate_limiter.is_allowed(client_ip):
            raise RateLimitExceededException("请求频率过高，请稍后再试")

        # API Key验证
        if not x_api_key:
            raise AuthenticationException("缺少API Key")

        if x_api_key != expected:
            raise AuthenticationException("无效的API Key")

    return _require


def get_client_ip(request: Request) -> str:
    """获取客户端IP地址"""
    # 检查代理头
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # 回退到直接连接IP
    return request.client.host if request.client else "unknown"


class EnhancedHTTPBearer(HTTPBearer):
    """增强的HTTP Bearer认证"""

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        # 速率限制检查
        client_ip = get_client_ip(request)
        if not _rate_limiter.is_allowed(client_ip):
            raise RateLimitExceededException("请求频率过高，请稍后再试")

        return await super().__call__(request)


def validate_api_key(api_key: str) -> bool:
    """验证API Key格式和有效性"""
    if not api_key:
        return False

    # 基本格式检查
    if len(api_key) < 8 or len(api_key) > 128:
        return False

    # 检查是否包含危险字符
    dangerous_chars = ['<', '>', '"', "'", '&', '\\', '/', '|', '*', '?', ':']
    for char in dangerous_chars:
        if char in api_key:
            return False

    return True


def create_secure_headers() -> Dict[str, str]:
    """创建安全响应头"""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": "default-src 'self'",
    }






