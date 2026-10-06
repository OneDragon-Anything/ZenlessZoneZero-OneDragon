from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.envs.recovery_repair_service import (
    RecoveryRepairEvent,
    RecoveryRepairService,
)


class RecoveryRepairQtAdapter(QObject):
    """把恢复重装服务的回调转成 Qt 信号。"""

    event_received = Signal(object)
    restart_requested = Signal()

    def __init__(
        self,
        ctx: OneDragonEnvContext,
        restart_callback: Callable[[], None],
        parent: QObject | None = None,
    ) -> None:
        """创建恢复服务和 Qt 信号之间的适配器。"""
        super().__init__(parent)
        self.restart_requested.connect(restart_callback)
        self.service = RecoveryRepairService(
            ctx,
            event_callback=self.event_received.emit,
            restart_callback=self.restart_requested.emit,
        )

    def start(self, target: str) -> bool:
        """按版本通道开始一键重装。"""
        return self.service.start(target)

    def cancel(self) -> None:
        """请求取消。"""
        self.service.cancel()

    def respond_force_confirmation(self, approved: bool) -> None:
        """回应工作区覆盖确认。"""
        self.service.respond_force_confirmation(approved)

    def is_active(self) -> bool:
        """返回重装是否仍在执行。"""
        return self.service.is_active()

    def on_event(self, event: RecoveryRepairEvent) -> None:
        """保留统一事件入口供需要时转发。"""
        self.event_received.emit(event)
