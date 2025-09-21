"""
统一API监控系统
提供API调用指标收集、WebSocket监控、结构化日志记录和健康检查功能
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from threading import Lock

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from zzz_od.api.ws import manager as ws_manager
from zzz_od.api.run_registry import get_global_run_registry


@dataclass
class APIMetrics:
    """API调用指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    max_response_time: float = 0.0
    min_response_time: float = float('inf')
    avg_response_time: float = 0.0
    requests_per_minute: int = 0
    error_rate: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class WebSocketMetrics:
    """WebSocket连接指标"""
    total_connections: int = 0
    active_connections: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    messages_dropped: int = 0
    connection_errors: int = 0
    average_message_size: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ModuleMetrics:
    """模块运行指标"""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    active_runs: int = 0
    average_run_duration: float = 0.0
    last_run_time: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)


class StructuredLogger:
    """结构化日志记录器"""

    def __init__(self):
        self.logger = logging.getLogger("unified_api_monitor")
        self.logger.setLevel(logging.INFO)

        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # 添加控制台处理器
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_api_call(self, method: str, path: str, status_code: int,
                    response_time: float, run_id: Optional[str] = None,
                    error: Optional[str] = None):
        """记录API调用日志"""
        log_data = {
            "type": "api_call",
            "method": method,
            "path": path,
            "status_code": status_code,
            "response_time_ms": response_time * 1000,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        if run_id:
            log_data["runId"] = run_id

        if error:
            log_data["error"] = error
            log_data["stack_trace"] = traceback.format_exc()

        level = "ERROR" if status_code >= 400 else "INFO"
        self.logger.log(
            getattr(logging, level),
            f"API调用 {method} {path} - {status_code} ({response_time*1000:.2f}ms)",
            extra={"structured_data": log_data}
        )

    def log_websocket_event(self, event_type: str, channel: str,
                           connection_count: int, message_count: int = 0,
                           run_id: Optional[str] = None, error: Optional[str] = None):
        """记录WebSocket事件日志"""
        log_data = {
            "type": "websocket_event",
            "event_type": event_type,
            "channel": channel,
            "connection_count": connection_count,
            "message_count": message_count,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        if run_id:
            log_data["runId"] = run_id

        if error:
            log_data["error"] = error
            log_data["stack_trace"] = traceback.format_exc()

        level = "ERROR" if error else "INFO"
        self.logger.log(
            getattr(logging, level),
            f"WebSocket事件 {event_type} - {channel} ({connection_count}连接)",
            extra={"structured_data": log_data}
        )

    def log_module_event(self, module_name: str, event_type: str,
                        run_id: Optional[str] = None, duration: Optional[float] = None,
                        error: Optional[str] = None):
        """记录模块事件日志"""
        log_data = {
            "type": "module_event",
            "module": module_name,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        if run_id:
            log_data["runId"] = run_id

        if duration is not None:
            log_data["duration_seconds"] = duration

        if error:
            log_data["error"] = error
            log_data["stack_trace"] = traceback.format_exc()

        level = "ERROR" if error else "INFO"
        self.logger.log(
            getattr(logging, level),
            f"模块事件 {module_name} - {event_type}",
            extra={"structured_data": log_data}
        )


class UnifiedMonitor:
    """统一监控系统"""

    def __init__(self):
        self.api_metrics: Dict[str, APIMetrics] = defaultdict(APIMetrics)
        self.websocket_metrics: Dict[str, WebSocketMetrics] = defaultdict(WebSocketMetrics)
        self.module_metrics: Dict[str, ModuleMetrics] = defaultdict(ModuleMetrics)
        self.structured_logger = StructuredLogger()
        self._lock = Lock()

        # 时间窗口数据（用于计算每分钟请求数等）
        self.request_timestamps: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.window_size = timedelta(minutes=1)

    def record_api_call(self, endpoint: str, method: str, status_code: int,
                       response_time: float, run_id: Optional[str] = None,
                       error: Optional[str] = None):
        """记录API调用指标"""
        with self._lock:
            key = f"{method}:{endpoint}"
            metrics = self.api_metrics[key]
            current_time = datetime.now()

            # 更新基本指标
            metrics.total_requests += 1
            metrics.total_response_time += response_time

            if status_code < 400:
                metrics.successful_requests += 1
            else:
                metrics.failed_requests += 1

            # 更新响应时间统计
            metrics.max_response_time = max(metrics.max_response_time, response_time)
            metrics.min_response_time = min(metrics.min_response_time, response_time)
            metrics.avg_response_time = metrics.total_response_time / metrics.total_requests

            # 计算错误率
            metrics.error_rate = metrics.failed_requests / metrics.total_requests * 100

            # 更新时间窗口数据
            self.request_timestamps[key].append(current_time)

            # 计算每分钟请求数
            cutoff_time = current_time - self.window_size
            recent_requests = [ts for ts in self.request_timestamps[key] if ts > cutoff_time]
            metrics.requests_per_minute = len(recent_requests)

            metrics.last_updated = current_time

        # 记录结构化日志
        self.structured_logger.log_api_call(
            method, endpoint, status_code, response_time, run_id, error
        )

    def record_websocket_event(self, channel: str, event_type: str,
                              message_count: int = 0, run_id: Optional[str] = None,
                              error: Optional[str] = None):
        """记录WebSocket事件指标"""
        with self._lock:
            metrics = self.websocket_metrics[channel]
            current_time = datetime.now()

            if event_type == "connect":
                metrics.total_connections += 1
                metrics.active_connections += 1
            elif event_type == "disconnect":
                metrics.active_connections = max(0, metrics.active_connections - 1)
            elif event_type == "message_sent":
                metrics.messages_sent += message_count
            elif event_type == "message_received":
                metrics.messages_received += message_count
            elif event_type == "message_dropped":
                metrics.messages_dropped += message_count
            elif event_type == "error":
                metrics.connection_errors += 1

            metrics.last_updated = current_time

        # 记录结构化日志
        self.structured_logger.log_websocket_event(
            event_type, channel, metrics.active_connections, message_count, run_id, error
        )

    def record_module_event(self, module_name: str, event_type: str,
                           run_id: Optional[str] = None, duration: Optional[float] = None,
                           error: Optional[str] = None):
        """记录模块事件指标"""
        with self._lock:
            metrics = self.module_metrics[module_name]
            current_time = datetime.now()

            if event_type == "start":
                metrics.total_runs += 1
                metrics.active_runs += 1
                metrics.last_run_time = current_time
            elif event_type == "complete":
                metrics.successful_runs += 1
                metrics.active_runs = max(0, metrics.active_runs - 1)
                if duration is not None:
                    # 更新平均运行时间
                    total_duration = metrics.average_run_duration * (metrics.successful_runs - 1) + duration
                    metrics.average_run_duration = total_duration / metrics.successful_runs
            elif event_type == "failed":
                metrics.failed_runs += 1
                metrics.active_runs = max(0, metrics.active_runs - 1)

            metrics.last_updated = current_time

        # 记录结构化日志
        self.structured_logger.log_module_event(
            module_name, event_type, run_id, duration, error
        )

    def get_api_metrics(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """获取API指标"""
        with self._lock:
            if endpoint:
                return {endpoint: self.api_metrics.get(endpoint, APIMetrics()).__dict__}
            return {k: v.__dict__ for k, v in self.api_metrics.items()}

    def get_websocket_metrics(self, channel: Optional[str] = None) -> Dict[str, Any]:
        """获取WebSocket指标"""
        with self._lock:
            if channel:
                return {channel: self.websocket_metrics.get(channel, WebSocketMetrics()).__dict__}
            return {k: v.__dict__ for k, v in self.websocket_metrics.items()}

    def get_module_metrics(self, module: Optional[str] = None) -> Dict[str, Any]:
        """获取模块指标"""
        with self._lock:
            if module:
                return {module: self.module_metrics.get(module, ModuleMetrics()).__dict__}
            return {k: v.__dict__ for k, v in self.module_metrics.items()}

    async def get_health_status(self) -> Dict[str, Any]:
        """获取系统健康状态"""
        # 获取WebSocket连接管理器状态
        ws_health = await ws_manager.health_check()

        # 获取运行注册表状态
        registry = get_global_run_registry()
        active_runs = len([run_id for run_id in registry.runs.keys()
                          if registry.is_running(run_id)])

        # 计算总体指标
        total_api_requests = sum(m.total_requests for m in self.api_metrics.values())
        total_api_errors = sum(m.failed_requests for m in self.api_metrics.values())
        overall_error_rate = (total_api_errors / total_api_requests * 100) if total_api_requests > 0 else 0

        total_ws_connections = sum(m.active_connections for m in self.websocket_metrics.values())
        total_ws_messages = sum(m.messages_sent for m in self.websocket_metrics.values())

        total_module_runs = sum(m.active_runs for m in self.module_metrics.values())

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "api": {
                "total_requests": total_api_requests,
                "total_errors": total_api_errors,
                "error_rate_percent": round(overall_error_rate, 2),
                "endpoints": len(self.api_metrics)
            },
            "websocket": {
                "total_connections": total_ws_connections,
                "total_messages_sent": total_ws_messages,
                "channels": len(self.websocket_metrics),
                "manager_status": ws_health
            },
            "modules": {
                "active_runs": total_module_runs,
                "registry_active_runs": active_runs,
                "monitored_modules": len(self.module_metrics)
            },
            "detailed_metrics": {
                "api": self.get_api_metrics(),
                "websocket": self.get_websocket_metrics(),
                "modules": self.get_module_metrics()
            }
        }


# 全局监控实例
monitor = UnifiedMonitor()


class APIMonitoringMiddleware(BaseHTTPMiddleware):
    """API监控中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        run_id = None
        error = None

        try:
            # 尝试从请求中提取runId
            if hasattr(request.state, 'run_id'):
                run_id = request.state.run_id

            response = await call_next(request)

        except Exception as e:
            error = str(e)
            # 创建错误响应
            from fastapi import HTTPException
            from fastapi.responses import JSONResponse

            if isinstance(e, HTTPException):
                response = JSONResponse(
                    status_code=e.status_code,
                    content={"detail": e.detail}
                )
            else:
                response = JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error"}
                )

        # 计算响应时间
        response_time = time.time() - start_time

        # 记录指标
        monitor.record_api_call(
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            response_time=response_time,
            run_id=run_id,
            error=error
        )

        return response


def setup_websocket_monitoring():
    """设置WebSocket监控"""
    original_connect = ws_manager.connect
    original_disconnect = ws_manager.disconnect
    original_broadcast_json = ws_manager.broadcast_json

    async def monitored_connect(channel: str, websocket, module_filter=None, run_id_filter=None):
        result = await original_connect(channel, websocket, module_filter, run_id_filter)
        monitor.record_websocket_event(channel, "connect", run_id=run_id_filter)
        return result

    def monitored_disconnect(channel: str, websocket):
        result = original_disconnect(channel, websocket)
        monitor.record_websocket_event(channel, "disconnect")
        return result

    async def monitored_broadcast_json(channel: str, payload: Dict):
        try:
            result = await original_broadcast_json(channel, payload)
            # 只在有活跃连接时记录消息发送事件
            connection_count = len(ws_manager.active_connections.get(channel, []))
            if connection_count > 0:
                # 使用try-except包装监控调用，避免干扰主要功能
                try:
                    monitor.record_websocket_event(
                        channel, "message_sent",
                        message_count=1,
                        run_id=payload.get('runId')
                    )
                except Exception:
                    pass  # 忽略监控错误
            return result
        except Exception as e:
            # 只记录真正的错误，不记录协程警告
            if not isinstance(e, RuntimeWarning):
                try:
                    monitor.record_websocket_event(
                        channel, "error",
                        run_id=payload.get('runId'),
                        error=str(e)
                    )
                except Exception:
                    pass  # 忽略监控错误
            raise

    # 替换原方法
    ws_manager.connect = monitored_connect
    ws_manager.disconnect = monitored_disconnect
    ws_manager.broadcast_json = monitored_broadcast_json


def setup_module_monitoring():
    """设置模块监控"""
    registry = get_global_run_registry()

    # 监控运行注册表事件
    original_create = registry.create
    original_cancel = registry.cancel

    def monitored_create(factory):
        run_id = original_create(factory)
        # 尝试从工厂函数中获取模块名
        module_name = getattr(factory, '__module__', 'unknown')
        monitor.record_module_event(module_name, "start", run_id=run_id)
        return run_id

    def monitored_cancel(run_id: str):
        result = original_cancel(run_id)
        # 获取模块名（这里需要从注册表中获取）
        module_name = "unknown"  # 实际实现中需要从注册表获取
        if result:
            monitor.record_module_event(module_name, "complete", run_id=run_id)
        else:
            monitor.record_module_event(module_name, "failed", run_id=run_id)
        return result

    registry.create = monitored_create
    registry.cancel = monitored_cancel