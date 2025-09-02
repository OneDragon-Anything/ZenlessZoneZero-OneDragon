from __future__ import annotations

from typing import Callable

from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.ws import manager
from zzz_od.api.status_builder import build_onedragon_aggregate
from zzz_od.context.zzz_context import ZContext
from one_dragon.base.operation.one_dragon_context import (
    ContextRunningStateEventEnum,
)
from one_dragon.base.operation.application_base import ApplicationEventId


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
            status_text = self.ctx.context_running_status_text
            agg = build_onedragon_aggregate(self.ctx)
            display_text = f"{status_text} ({int(agg['progress']*100)}%)"
            self.registry.update_message(self.run_id, display_text)
            self._send_structured("state", {"state": state.name, "text": display_text, "aggregate": agg})

        def on_app_event(self, event):  # bound method, has __self__
            app_id = event.data
            agg = build_onedragon_aggregate(self.ctx)
            self._send_structured("app", {"appId": app_id, "aggregate": agg})

    listener = _BridgeCallbacks(ctx, run_id, channel)

    ctx.listen_event(ContextRunningStateEventEnum.START_RUNNING.value, listener.on_running_state)
    ctx.listen_event(ContextRunningStateEventEnum.PAUSE_RUNNING.value, listener.on_running_state)
    ctx.listen_event(ContextRunningStateEventEnum.RESUME_RUNNING.value, listener.on_running_state)
    ctx.listen_event(ContextRunningStateEventEnum.STOP_RUNNING.value, listener.on_running_state)
    ctx.listen_event(ApplicationEventId.APPLICATION_START.value, listener.on_app_event)
    ctx.listen_event(ApplicationEventId.APPLICATION_STOP.value, listener.on_app_event)

    def _detach() -> None:
        try:
            ctx.unlisten_event(ContextRunningStateEventEnum.START_RUNNING.value, listener.on_running_state)
            ctx.unlisten_event(ContextRunningStateEventEnum.PAUSE_RUNNING.value, listener.on_running_state)
            ctx.unlisten_event(ContextRunningStateEventEnum.RESUME_RUNNING.value, listener.on_running_state)
            ctx.unlisten_event(ContextRunningStateEventEnum.STOP_RUNNING.value, listener.on_running_state)
            ctx.unlisten_event(ApplicationEventId.APPLICATION_START.value, listener.on_app_event)
            ctx.unlisten_event(ApplicationEventId.APPLICATION_STOP.value, listener.on_app_event)
        except Exception:
            pass

    registry.set_bridge(run_id, _detach)
    return _detach


