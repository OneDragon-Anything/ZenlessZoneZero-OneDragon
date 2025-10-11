from __future__ import annotations

from typing import Callable
from datetime import datetime
from enum import Enum

from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.ws import manager
from zzz_od.api.status_builder import build_onedragon_aggregate
from zzz_od.context.zzz_context import ZContext
from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContextStateEventEnum,
)
from one_dragon.base.operation.application_base import ApplicationEventId


class BattleAssistantEventType(str, Enum):
    """战斗助手事件类型"""
    BATTLE_STATE_CHANGED = "battle_state_changed"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    CONFIG_UPDATED = "config_updated"
    ERROR_OCCURRED = "error_occurred"


def attach_run_event_bridge(ctx: ZContext, run_id: str) -> Callable[[], None]:
    """
    将 ctx 的运行状态与应用事件桥接到 WS 通道 `/ws/v1/runs/{run_id}`，并同步到 RunRegistry。
    返回一个解除函数，在任务结束/取消时应被调用以移除监听。
    """

    registry = get_global_run_registry()
    channel = f"runs:{run_id}"

    class _BridgeCallbacks:
        def __init__(self, ctx: ZContext, run_id: str, channel: str):
            self.ctx = ctx
            self.run_id = run_id
            self.channel = channel
            self.registry = registry

        def _send(self, text: str) -> None:
            try:
                import asyncio
                asyncio.create_task(manager.broadcast(self.channel, text))
            except Exception:
                pass

        def _send_structured(self, event_type: str, data) -> None:
            try:
                import asyncio
                asyncio.create_task(manager.broadcast_json(self.channel, {"type": event_type, "data": data}))
            except Exception:
                pass

        def on_running_state(self, event):  # bound method, has __self__
            state = event.data
            status_text = getattr(self.ctx.run_context, "run_status_text", "")
            agg = build_onedragon_aggregate(self.ctx)
            display_text = f"{status_text} ({int(agg['progress']*100)}%)"
            self.registry.update_message(self.run_id, display_text)
            self._send_structured("state", {"state": state.name, "text": display_text, "aggregate": agg})

        def on_app_event(self, event):  # bound method, has __self__
            app_id = event.data
            agg = build_onedragon_aggregate(self.ctx)
            self._send_structured("app", {"appId": app_id, "aggregate": agg})

    listener = _BridgeCallbacks(ctx, run_id, channel)

    run_event_bus = ctx.run_context.event_bus
    run_event_bus.listen_event(ApplicationRunContextStateEventEnum.START.value, listener.on_running_state)
    run_event_bus.listen_event(ApplicationRunContextStateEventEnum.PAUSE.value, listener.on_running_state)
    run_event_bus.listen_event(ApplicationRunContextStateEventEnum.RESUME.value, listener.on_running_state)
    run_event_bus.listen_event(ApplicationRunContextStateEventEnum.STOP.value, listener.on_running_state)
    ctx.listen_event(ApplicationEventId.APPLICATION_START.value, listener.on_app_event)
    ctx.listen_event(ApplicationEventId.APPLICATION_STOP.value, listener.on_app_event)

    def _detach() -> None:
        try:
            run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.START.value, listener.on_running_state)
            run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.PAUSE.value, listener.on_running_state)
            run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.RESUME.value, listener.on_running_state)
            run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.STOP.value, listener.on_running_state)
            ctx.unlisten_event(ApplicationEventId.APPLICATION_START.value, listener.on_app_event)
            ctx.unlisten_event(ApplicationEventId.APPLICATION_STOP.value, listener.on_app_event)
        except Exception:
            pass

    registry.set_bridge(run_id, _detach)
    return _detach


def attach_battle_assistant_event_bridge(ctx: ZContext, run_id: str) -> Callable[[], None]:
    """
    为战斗助手创建专用的事件桥接，支持战斗状态更新和任务进度推送
    """

    registry = get_global_run_registry()
    task_channel = f"battle-assistant:tasks:{run_id}"
    events_channel = "battle-assistant:events"
    battle_state_channel = "battle-assistant:battle-state"

    class _BattleAssistantBridge:
        def __init__(self, ctx: ZContext, run_id: str):
            self.ctx = ctx
            self.run_id = run_id
            self.registry = registry
            self.last_battle_state = None

        def _broadcast_to_channels(self, event_type: str, data, include_battle_state: bool = False) -> None:
            """向相关通道广播事件"""
            try:
                import asyncio
                message = {
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.now().isoformat(),
                    "task_id": self.run_id
                }

                # 向任务专用通道广播
                asyncio.create_task(manager.broadcast_json(task_channel, message))

                # 向全局事件通道广播
                asyncio.create_task(manager.broadcast_json(events_channel, message))

                # 如果是战斗状态相关，也向战斗状态通道广播
                if include_battle_state:
                    asyncio.create_task(manager.broadcast_json(battle_state_channel, message))

            except Exception:
                pass

        def on_running_state(self, event):
            """处理运行状态变化"""
            state = event.data
            event_id = event.event_id
            status_text = getattr(self.ctx.run_context, "run_status_text", "")
            agg = build_onedragon_aggregate(self.ctx)

            event_data = {
                "state": state.name if hasattr(state, "name") else str(state),
                "text": status_text,
                "progress": agg.get('progress', 0.0),
                "aggregate": agg
            }

            if event_id == ApplicationRunContextStateEventEnum.START.value:
                self._broadcast_to_channels(BattleAssistantEventType.TASK_STARTED, event_data)
            elif event_id == ApplicationRunContextStateEventEnum.STOP.value:
                # 检查是否是正常完成还是错误停止
                if hasattr(self.ctx, 'last_error') and self.ctx.last_error:
                    self._broadcast_to_channels(BattleAssistantEventType.TASK_FAILED, {
                        **event_data,
                        "error": str(self.ctx.last_error)
                    })
                else:
                    self._broadcast_to_channels(BattleAssistantEventType.TASK_COMPLETED, event_data)
            else:
                self._broadcast_to_channels(BattleAssistantEventType.TASK_PROGRESS, event_data)

        def on_app_event(self, event):
            """处理应用事件"""
            app_id = event.data
            agg = build_onedragon_aggregate(self.ctx)

            event_data = {
                "appId": app_id,
                "aggregate": agg,
                "progress": agg.get('progress', 0.0)
            }

            self._broadcast_to_channels(BattleAssistantEventType.TASK_PROGRESS, event_data)

        def broadcast_battle_state(self, battle_state_data):
            """广播战斗状态更新"""
            # 只有当状态真正发生变化时才广播
            if self.last_battle_state != battle_state_data:
                self.last_battle_state = battle_state_data.copy() if isinstance(battle_state_data, dict) else battle_state_data
                self._broadcast_to_channels(
                    BattleAssistantEventType.BATTLE_STATE_CHANGED,
                    battle_state_data,
                    include_battle_state=True
                )

        def broadcast_config_update(self, config_type: str, config_data):
            """广播配置更新事件"""
            event_data = {
                "config_type": config_type,
                "config_data": config_data
            }
            self._broadcast_to_channels(BattleAssistantEventType.CONFIG_UPDATED, event_data)

        def broadcast_error(self, error_message: str, error_details=None):
            """广播错误事件"""
            event_data = {
                "message": error_message,
                "details": error_details
            }
            self._broadcast_to_channels(BattleAssistantEventType.ERROR_OCCURRED, event_data)

    bridge = _BattleAssistantBridge(ctx, run_id)

    # 监听上下文运行状态事件
    run_event_bus = ctx.run_context.event_bus
    run_event_bus.listen_event(ApplicationRunContextStateEventEnum.START.value, bridge.on_running_state)
    run_event_bus.listen_event(ApplicationRunContextStateEventEnum.PAUSE.value, bridge.on_running_state)
    run_event_bus.listen_event(ApplicationRunContextStateEventEnum.RESUME.value, bridge.on_running_state)
    run_event_bus.listen_event(ApplicationRunContextStateEventEnum.STOP.value, bridge.on_running_state)
    ctx.listen_event(ApplicationEventId.APPLICATION_START.value, bridge.on_app_event)
    ctx.listen_event(ApplicationEventId.APPLICATION_STOP.value, bridge.on_app_event)

    def _detach() -> None:
        try:
            run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.START.value, bridge.on_running_state)
            run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.PAUSE.value, bridge.on_running_state)
            run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.RESUME.value, bridge.on_running_state)
            run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.STOP.value, bridge.on_running_state)
            ctx.unlisten_event(ApplicationEventId.APPLICATION_START.value, bridge.on_app_event)
            ctx.unlisten_event(ApplicationEventId.APPLICATION_STOP.value, bridge.on_app_event)
        except Exception:
            pass

    # 将桥接对象存储到上下文中，以便后续使用
    setattr(ctx, '_battle_assistant_bridge', bridge)

    registry.set_bridge(run_id, _detach)
    return _detach


def broadcast_battle_assistant_event(event_type: str, data, task_id: str = None):
    """
    全局函数，用于从任何地方广播战斗助手事件
    """
    try:
        import asyncio
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id
        }

        # 向全局事件通道广播
        asyncio.create_task(manager.broadcast_json("battle-assistant:events", message))

        # 如果指定了任务ID，也向任务专用通道广播
        if task_id:
            asyncio.create_task(manager.broadcast_json(f"battle-assistant:tasks:{task_id}", message))

    except Exception:
        pass


