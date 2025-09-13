from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from .security import get_api_key_dependency


router = APIRouter(prefix="/ws/v1", tags=["ws"], dependencies=[Depends(get_api_key_dependency())])


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(channel, []).append(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        conns = self.active_connections.get(channel)
        if not conns:
            return
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self.active_connections.pop(channel, None)

    async def broadcast(self, channel: str, message: str) -> None:
        for ws in list(self.active_connections.get(channel, [])):
            try:
                await ws.send_text(message)
            except Exception:
                # best-effort
                pass

    async def broadcast_json(self, channel: str, payload) -> None:
        for ws in list(self.active_connections.get(channel, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/runs/{run_id}")
async def runs_ws(websocket: WebSocket, run_id: str):
    channel = f"runs:{run_id}"
    await manager.connect(channel, websocket)
    try:
        # 简化占位：保持连接存活
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


@router.websocket("/logs")
async def logs_ws(websocket: WebSocket):
    """实时日志通道: 连接后即可接收 type=log 消息, 客户端可定期发送 ping 保持连接."""
    channel = "logs"
    await manager.connect(channel, websocket)
    try:
        while True:
            # 接收客户端心跳/忽略内容
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


@router.websocket("/battle-assistant/tasks/{task_id}")
async def battle_assistant_task_ws(websocket: WebSocket, task_id: str):
    """战斗助手任务事件通道: 订阅特定任务的进度和状态更新"""
    channel = f"battle-assistant:tasks:{task_id}"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


@router.websocket("/battle-assistant/events")
async def battle_assistant_events_ws(websocket: WebSocket):
    """战斗助手全局事件通道: 订阅所有战斗助手相关事件"""
    channel = "battle-assistant:events"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


@router.websocket("/battle-assistant/battle-state")
async def battle_assistant_battle_state_ws(websocket: WebSocket):
    """战斗状态实时更新通道: 订阅战斗状态变化"""
    channel = "battle-assistant:battle-state"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


