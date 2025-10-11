from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, Callable

from pydantic import BaseModel

from zzz_od.api.run_registry import get_global_run_registry
from zzz_od.api.ws import manager
from zzz_od.api.monitoring import monitor
from zzz_od.api.log_storage import get_global_log_storage
from zzz_od.api.models import LogLevelEnum
from zzz_od.context.zzz_context import ZContext
from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContextStateEventEnum,
)
from one_dragon.base.operation.application_base import ApplicationEventId


class WSEventType(str, Enum):
    """统一WebSocket事件类型"""
    STATUS_UPDATE = "status_update"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    RUN_LOG = "run_log"


class WSEventData(BaseModel):
    """WebSocket事件数据"""
    # status_update
    is_running: Optional[bool] = None
    context_state: Optional[str] = None
    running_tasks: Optional[int] = None
    message: Optional[str] = None

    # task events
    taskName: Optional[str] = None
    error: Optional[str] = None

    # run_log
    level: Optional[str] = None  # debug|info|warning|error
    extra: Optional[Dict[str, Any]] = None


class WSEvent(BaseModel):
    """统一WebSocket事件"""
    type: WSEventType
    module: str
    runId: Optional[str] = None
    timestamp: str
    data: WSEventData
    seq: Optional[int] = None  # 可选序列号，每个runId单调递增


class UnifiedEventBridge:
    """统一事件桥接器"""

    def __init__(self, ctx: ZContext, run_id: str, module_name: str):
        self.ctx = ctx
        self.run_id = run_id
        self.module_name = module_name
        self.registry = get_global_run_registry()
        self.seq_counter = 0
        self._setup_listeners()

    def _get_next_seq(self) -> int:
        """获取下一个序列号"""
        self.seq_counter += 1
        return self.seq_counter

    def _send_event(self, event_type: WSEventType, data: WSEventData) -> None:
        """发送统一格式的WebSocket事件"""
        try:
            event = WSEvent(
                type=event_type,
                module=self.module_name,
                runId=self.run_id,
                timestamp=datetime.now(datetime.UTC).isoformat() + "Z",
                data=data,
                seq=self._get_next_seq()
            )

            # 发送到统一WebSocket通道
            channel = f"unified:v1"
            task1 = asyncio.create_task(manager.broadcast_json(channel, event.dict()))
            task1.add_done_callback(lambda t: None)  # 防止协程警告

            # 也发送到模块专用通道（兼容性）
            module_channel = f"{self.module_name}:{self.run_id}"
            task2 = asyncio.create_task(manager.broadcast_json(module_channel, event.dict()))
            task2.add_done_callback(lambda t: None)  # 防止协程警告

            # 记录WebSocket事件到监控系统（带错误处理）
            try:
                monitor.record_websocket_event(
                    channel, "message_sent",
                    message_count=1,
                    run_id=self.run_id
                )
            except Exception:
                pass  # 忽略监控错误，不影响主要功能

        except Exception as e:
            # 记录WebSocket错误事件（带错误处理）
            try:
                monitor.record_websocket_event(
                    f"unified:v1", "error",
                    run_id=self.run_id,
                    error=str(e)
                )
            except Exception:
                pass  # 忽略监控错误

            # 同时记录到日志
            import logging
            logging.getLogger("unified_event_bridge").error(f"WebSocket广播失败: {e}")

    def send_status_update(self, is_running: bool, context_state: str, **kwargs):
        """发送状态更新事件"""
        data = WSEventData(
            is_running=is_running,
            context_state=context_state,
            running_tasks=kwargs.get('running_tasks'),
            message=kwargs.get('message')
        )
        self._send_event(WSEventType.STATUS_UPDATE, data)

    def send_task_started(self, task_name: str = None, message: str = None):
        """发送任务开始事件"""
        data = WSEventData(
            taskName=task_name,
            message=message
        )
        self._send_event(WSEventType.TASK_STARTED, data)

    def send_task_completed(self, task_name: str = None, message: str = None):
        """发送任务完成事件"""
        data = WSEventData(
            taskName=task_name,
            message=message
        )
        self._send_event(WSEventType.TASK_COMPLETED, data)

    def send_task_failed(self, task_name: str = None, error: str = None):
        """发送任务失败事件"""
        data = WSEventData(
            taskName=task_name,
            error=error,
            message=f"任务失败: {error}" if error else "任务失败"
        )
        self._send_event(WSEventType.TASK_FAILED, data)

    def send_run_log(self, level: str, message: str, extra: Dict = None):
        """发送运行日志事件"""
        data = WSEventData(
            level=level,
            message=message,
            extra=extra
        )

        # 发送WebSocket事件
        self._send_event(WSEventType.RUN_LOG, data)

        # 同时保存到日志存储中
        try:
            log_storage = get_global_log_storage()
            # 转换level为枚举类型
            log_level = LogLevelEnum.INFO  # 默认值
            if level:
                level_upper = level.upper()
                if level_upper in [e.value.upper() for e in LogLevelEnum]:
                    log_level = LogLevelEnum(level_upper.lower())

            log_storage.add_log(
                runId=self.run_id,
                module=self.module_name,
                level=log_level,
                message=message,
                seq=self.seq_counter,  # 使用当前序列号
                extra=extra
            )
        except Exception as e:
            # 日志存储失败不应该影响WebSocket事件发送
            monitor.record_websocket_event(
                f"unified:v1", "log_storage_error",
                run_id=self.run_id,
                error=str(e)
            )

    def _setup_listeners(self):
        """设置事件监听器"""
        run_event_bus = self.ctx.run_context.event_bus
        run_event_bus.listen_event(ApplicationRunContextStateEventEnum.START.value, self._on_running_state)
        run_event_bus.listen_event(ApplicationRunContextStateEventEnum.PAUSE.value, self._on_running_state)
        run_event_bus.listen_event(ApplicationRunContextStateEventEnum.RESUME.value, self._on_running_state)
        run_event_bus.listen_event(ApplicationRunContextStateEventEnum.STOP.value, self._on_running_state)
        self.ctx.listen_event(ApplicationEventId.APPLICATION_START.value, self._on_app_event)
        self.ctx.listen_event(ApplicationEventId.APPLICATION_STOP.value, self._on_app_event)
        self._run_event_bus = run_event_bus

    def _on_running_state(self, event):
        """处理运行状态变化"""
        state = event.data
        event_id = event.event_id
        status_text = getattr(self.ctx.run_context, "run_status_text", "")

        # 更新注册表中的消息
        self.registry.update_message(self.run_id, status_text)

        # 发送状态更新事件
        context_state = "idle"
        is_running = False

        if event_id == ApplicationRunContextStateEventEnum.START.value:
            context_state = "running"
            is_running = True
            self.send_task_started(message=status_text)
        elif event_id == ApplicationRunContextStateEventEnum.PAUSE.value:
            context_state = "paused"
            is_running = True
        elif event_id == ApplicationRunContextStateEventEnum.RESUME.value:
            context_state = "running"
            is_running = True
        elif event_id == ApplicationRunContextStateEventEnum.STOP.value:
            context_state = "idle"
            is_running = False
            # 检查是否是错误停止
            if hasattr(self.ctx, 'last_error') and self.ctx.last_error:
                self.send_task_failed(error=str(self.ctx.last_error))
            else:
                self.send_task_completed(message="任务完成")

        self.send_status_update(
            is_running=is_running,
            context_state=context_state,
            message=status_text
        )

    def _on_app_event(self, event):
        """处理应用事件"""
        app_id = event.data
        if event.event_id == ApplicationEventId.APPLICATION_START.value:
            self.send_task_started(task_name=app_id, message=f"开始执行 {app_id}")
        elif event.event_id == ApplicationEventId.APPLICATION_STOP.value:
            self.send_task_completed(task_name=app_id, message=f"完成执行 {app_id}")

    def detach(self):
        """解除事件监听"""
        try:
            if hasattr(self, "_run_event_bus"):
                self._run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.START.value, self._on_running_state)
                self._run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.PAUSE.value, self._on_running_state)
                self._run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.RESUME.value, self._on_running_state)
                self._run_event_bus.unlisten_event(ApplicationRunContextStateEventEnum.STOP.value, self._on_running_state)
            self.ctx.unlisten_event(ApplicationEventId.APPLICATION_START.value, self._on_app_event)
            self.ctx.unlisten_event(ApplicationEventId.APPLICATION_STOP.value, self._on_app_event)
        except Exception:
            pass


def attach_unified_event_bridge(ctx: ZContext, run_id: str, module_name: str) -> Callable[[], None]:
    """
    为指定模块附加统一事件桥接器

    Args:
        ctx: 上下文对象
        run_id: 运行ID
        module_name: 模块名称

    Returns:
        解除函数
    """
    bridge = UnifiedEventBridge(ctx, run_id, module_name)

    # 将桥接器存储到注册表中
    registry = get_global_run_registry()
    registry.set_bridge(run_id, bridge.detach)

    return bridge.detach
