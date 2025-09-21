from __future__ import annotations

import asyncio
import json
import time
from typing import Dict, List, Optional, Set
from collections import defaultdict, deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query

import os
from .security import get_api_key_dependency
from .unified_errors import AuthenticationException


router = APIRouter(prefix="/ws", tags=["ws"])


async def authenticate_websocket(websocket: WebSocket) -> bool:
    """
    WebSocket认证检查
    如果设置了OD_API_KEY环境变量，则需要在查询参数中提供api_key
    """
    expected_key = os.getenv("OD_API_KEY")
    if not expected_key:
        # 没有设置API密钥，允许连接
        return True

    # 从查询参数中获取API密钥
    query_params = dict(websocket.query_params)
    provided_key = query_params.get("api_key")

    if not provided_key or provided_key != expected_key:
        await websocket.close(code=1008, reason="Authentication failed")
        return False

    return True


class RateLimiter:
    """简单的令牌桶限流器"""

    def __init__(self, max_tokens: int = 200, refill_rate: float = 200.0):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = max_tokens
        self.last_refill = time.time()

    def can_consume(self, tokens: int = 1) -> bool:
        """检查是否可以消费指定数量的令牌"""
        now = time.time()
        # 补充令牌
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class MessageBatcher:
    """消息批量处理器"""

    def __init__(self, batch_size: int = 50, batch_interval_ms: int = 50):
        self.batch_size = batch_size
        self.batch_interval = batch_interval_ms / 1000.0  # 转换为秒
        self.pending_messages: Dict[str, List[Dict]] = defaultdict(list)
        self.batch_timers: Dict[str, asyncio.Task] = {}

    async def add_message(self, channel: str, payload: Dict, manager: 'ConnectionManager'):
        """添加消息到批处理队列"""
        self.pending_messages[channel].append(payload)

        # 如果达到批量大小，立即发送
        if len(self.pending_messages[channel]) >= self.batch_size:
            await self._flush_channel(channel, manager)
        else:
            # 设置定时器
            if channel not in self.batch_timers:
                self.batch_timers[channel] = asyncio.create_task(
                    self._schedule_flush(channel, manager)
                )

    async def _schedule_flush(self, channel: str, manager: 'ConnectionManager'):
        """定时刷新通道消息"""
        await asyncio.sleep(self.batch_interval)
        await self._flush_channel(channel, manager)

    async def _flush_channel(self, channel: str, manager: 'ConnectionManager'):
        """刷新指定通道的消息"""
        if channel in self.batch_timers:
            self.batch_timers[channel].cancel()
            del self.batch_timers[channel]

        messages = self.pending_messages.pop(channel, [])
        if messages:
            await manager._broadcast_batch(channel, messages)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.connection_filters: Dict[WebSocket, Dict[str, Set[str]]] = {}  # ws -> {module: {runIds}}
        self.rate_limiters: Dict[WebSocket, RateLimiter] = {}
        self.message_batcher = MessageBatcher()
        self.max_message_size_kb = 8
        self.connection_stats: Dict[str, Dict] = defaultdict(lambda: {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_dropped': 0,
            'errors': 0
        })

    async def connect(self, channel: str, websocket: WebSocket,
                     module_filter: Optional[str] = None,
                     run_id_filter: Optional[str] = None,
                     skip_accept: bool = False) -> None:
        """连接WebSocket并设置过滤器"""
        try:
            # 只在第一次连接时accept
            if not skip_accept:
                await websocket.accept()
            self.active_connections.setdefault(channel, []).append(websocket)
            # 只在第一次设置rate limiter
            if websocket not in self.rate_limiters:
                self.rate_limiters[websocket] = RateLimiter()

            # 更新统计信息
            stats = self.connection_stats[channel]
            stats['total_connections'] += 1
            stats['active_connections'] = len(self.active_connections.get(channel, []))

            # 设置过滤器
            if module_filter or run_id_filter:
                filters = self.connection_filters.setdefault(websocket, {})
                if module_filter:
                    run_ids = {run_id_filter} if run_id_filter else set()
                    filters[module_filter] = run_ids

        except Exception as e:
            self.connection_stats[channel]['errors'] += 1
            raise

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        """断开WebSocket连接"""
        conns = self.active_connections.get(channel)
        if conns and websocket in conns:
            conns.remove(websocket)

        # 更新统计信息
        stats = self.connection_stats[channel]
        stats['active_connections'] = len(self.active_connections.get(channel, []))

        if not conns:
            self.active_connections.pop(channel, None)

        # 清理过滤器和限流器
        self.connection_filters.pop(websocket, None)
        self.rate_limiters.pop(websocket, None)

    def _should_send_to_connection(self, websocket: WebSocket, payload: Dict) -> bool:
        """检查是否应该向连接发送消息"""
        filters = self.connection_filters.get(websocket)
        if not filters:
            return True  # 无过滤器，发送所有消息

        module = payload.get('module')
        run_id = payload.get('runId')

        if not module:
            return True  # 无模块信息，发送

        if module not in filters:
            return False  # 模块不在过滤器中

        run_ids = filters[module]
        if not run_ids:
            return True  # 模块匹配且无runId过滤

        return run_id in run_ids  # 检查runId是否匹配

    def _validate_message_size(self, payload: Dict) -> bool:
        """验证消息大小"""
        try:
            message_size = len(json.dumps(payload).encode('utf-8'))
            return message_size <= self.max_message_size_kb * 1024
        except Exception:
            return False

    async def broadcast(self, channel: str, message: str) -> None:
        """广播文本消息"""
        stats = self.connection_stats[channel]

        for ws in list(self.active_connections.get(channel, [])):
            try:
                limiter = self.rate_limiters.get(ws)
                if limiter and not limiter.can_consume():
                    stats['messages_dropped'] += 1
                    continue  # 跳过限流的连接

                await ws.send_text(message)
                stats['messages_sent'] += 1
            except Exception:
                stats['errors'] += 1
                # 连接可能已断开，从活跃连接中移除
                self._cleanup_dead_connection(channel, ws)

    async def broadcast_json(self, channel: str, payload: Dict) -> None:
        """广播JSON消息（支持批处理）"""
        if not self._validate_message_size(payload):
            return  # 消息过大，跳过

        # 使用批处理器
        await self.message_batcher.add_message(channel, payload, self)

    async def _broadcast_batch(self, channel: str, messages: List[Dict]) -> None:
        """批量广播消息"""
        stats = self.connection_stats[channel]

        for ws in list(self.active_connections.get(channel, [])):
            try:
                limiter = self.rate_limiters.get(ws)
                if limiter and not limiter.can_consume(len(messages)):
                    stats['messages_dropped'] += len(messages)
                    continue  # 跳过限流的连接

                # 过滤消息
                filtered_messages = [
                    msg for msg in messages
                    if self._should_send_to_connection(ws, msg)
                ]

                if filtered_messages:
                    if len(filtered_messages) == 1:
                        await ws.send_json(filtered_messages[0])
                        stats['messages_sent'] += 1
                    else:
                        # 发送批量消息
                        await ws.send_json({
                            "type": "batch",
                            "messages": filtered_messages
                        })
                        stats['messages_sent'] += len(filtered_messages)
            except Exception:
                stats['errors'] += 1
                # 连接可能已断开，从活跃连接中移除
                self._cleanup_dead_connection(channel, ws)

    async def broadcast_with_filter(self, channel: str, payload: Dict,
                                  module_filter: Optional[str] = None,
                                  run_id_filter: Optional[str] = None) -> None:
        """带过滤器的广播"""
        if not self._validate_message_size(payload):
            self.connection_stats[channel]['messages_dropped'] += 1
            return

        stats = self.connection_stats[channel]

        for ws in list(self.active_connections.get(channel, [])):
            try:
                limiter = self.rate_limiters.get(ws)
                if limiter and not limiter.can_consume():
                    stats['messages_dropped'] += 1
                    continue

                # 检查过滤器
                if module_filter and payload.get('module') != module_filter:
                    continue
                if run_id_filter and payload.get('runId') != run_id_filter:
                    continue

                if self._should_send_to_connection(ws, payload):
                    await ws.send_json(payload)
                    stats['messages_sent'] += 1
            except Exception:
                stats['errors'] += 1
                # 连接可能已断开，从活跃连接中移除
                self._cleanup_dead_connection(channel, ws)

    def _cleanup_dead_connection(self, channel: str, websocket: WebSocket) -> None:
        """清理死连接"""
        try:
            conns = self.active_connections.get(channel, [])
            if websocket in conns:
                conns.remove(websocket)
                self.connection_stats[channel]['active_connections'] = len(conns)

            # 清理相关数据
            self.connection_filters.pop(websocket, None)
            self.rate_limiters.pop(websocket, None)
        except Exception:
            pass

    def get_connection_stats(self, channel: Optional[str] = None) -> Dict:
        """获取连接统计信息"""
        if channel:
            return dict(self.connection_stats.get(channel, {}))
        return {ch: dict(stats) for ch, stats in self.connection_stats.items()}

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        total_connections = sum(len(conns) for conns in self.active_connections.values())
        total_channels = len(self.active_connections)

        return {
            "status": "healthy",
            "total_connections": total_connections,
            "total_channels": total_channels,
            "channels": list(self.active_connections.keys()),
            "stats": self.get_connection_stats()
        }


manager = ConnectionManager()


@router.websocket("/v1/runs/{run_id}")
async def runs_ws(websocket: WebSocket, run_id: str):
    if not await authenticate_websocket(websocket):
        return

    channel = f"runs:{run_id}"
    await manager.connect(channel, websocket)
    try:
        # 简化占位：保持连接存活
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


@router.websocket("/v1/logs")
async def logs_ws(websocket: WebSocket):
    """实时日志通道: 连接后即可接收 type=log 消息, 客户端可定期发送 ping 保持连接."""
    if not await authenticate_websocket(websocket):
        return

    channel = "logs"
    await manager.connect(channel, websocket)
    try:
        while True:
            # 接收客户端心跳/忽略内容
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


@router.websocket("/v1/battle-assistant/tasks/{task_id}")
async def battle_assistant_task_ws(websocket: WebSocket, task_id: str):
    """战斗助手任务事件通道: 订阅特定任务的进度和状态更新"""
    if not await authenticate_websocket(websocket):
        return

    channel = f"battle-assistant:tasks:{task_id}"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


@router.websocket("/v1/battle-assistant/events")
async def battle_assistant_events_ws(websocket: WebSocket):
    """战斗助手全局事件通道: 订阅所有战斗助手相关事件"""
    if not await authenticate_websocket(websocket):
        return

    channel = "battle-assistant:events"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


@router.websocket("/v1/battle-assistant/battle-state")
async def battle_assistant_battle_state_ws(websocket: WebSocket):
    """战斗状态实时更新通道: 订阅战斗状态变化"""
    if not await authenticate_websocket(websocket):
        return

    channel = "battle-assistant:battle-state"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


async def unified_ws_impl(websocket: WebSocket, module: Optional[str], runId: Optional[str]):
    """统一WebSocket端点的实现"""
    if not await authenticate_websocket(websocket):
        return

    # 连接到多个通道：unified:v1 和 logs
    channel = "unified:v1"
    await manager.connect(channel, websocket, module, runId, skip_accept=False)
    # 同时连接到logs通道以接收日志消息，skip_accept=True避免重复accept
    await manager.connect("logs", websocket, skip_accept=True)

    try:
        while True:
            message = await websocket.receive_text()

            # 处理心跳消息
            if message == "ping":
                await websocket.send_text("pong")
            elif message.startswith("subscribe:"):
                # 处理订阅消息，格式: subscribe:module:runId
                parts = message.split(":", 2)
                if len(parts) >= 2:
                    sub_module = parts[1] if len(parts) > 1 and parts[1] else None
                    sub_run_id = parts[2] if len(parts) > 2 and parts[2] else None

                    # 更新连接过滤器
                    if sub_module:
                        filters = manager.connection_filters.setdefault(websocket, {})
                        run_ids = {sub_run_id} if sub_run_id else set()
                        filters[sub_module] = run_ids

                    await websocket.send_json({
                        "type": "subscription_confirmed",
                        "module": sub_module,
                        "runId": sub_run_id
                    })
            # 忽略其他消息

    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)
        manager.disconnect("logs", websocket)  # 也断开logs通道
    except Exception as e:
        # 优雅降级：记录错误但不中断其他连接
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
        finally:
            manager.disconnect(channel, websocket)
            manager.disconnect("logs", websocket)  # 也断开logs通道


@router.websocket("/v1")
async def unified_ws_no_slash(websocket: WebSocket,
                             module: Optional[str] = Query(None, description="模块过滤器"),
                             runId: Optional[str] = Query(None, description="运行ID过滤器")):
    """统一WebSocket端点（无末尾斜杠），支持ping/pong心跳和消息过滤"""
    await unified_ws_impl(websocket, module, runId)


@router.websocket("/v1/")
async def unified_ws(websocket: WebSocket,
                    module: Optional[str] = Query(None, description="模块过滤器"),
                    runId: Optional[str] = Query(None, description="运行ID过滤器")):
    """统一WebSocket端点，支持ping/pong心跳和消息过滤"""
    await unified_ws_impl(websocket, module, runId)


