from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from typing import TYPE_CHECKING

from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_screen import expected_map, read_area
from zzz_od.operation.zzz_operation import ZOperation

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from one_dragon.base.operation.context_event_bus import ContextEventItem
    from one_dragon.base.operation.operation import Operation
    from one_dragon.base.operation.operation_base import OperationResult


class _BagelRunEvents:
    """贝果单次执行的事件订阅，关闭后拒绝已经排队的旧回调。"""

    def __init__(
        self,
        on_pause: Callable[[ContextEventItem | None], None],
        on_resume: Callable[[ContextEventItem | None], None],
    ) -> None:
        """保留原有暂停恢复行为，每次执行单独创建。"""
        self.on_pause: Callable[[ContextEventItem | None], None] = on_pause
        self.on_resume: Callable[[ContextEventItem | None], None] = on_resume
        self.lock: RLock = RLock()
        self.active: bool = True

    def pause(self, event: ContextEventItem | None = None) -> None:
        """暂停清理与关闭互斥，避免操作结束后继续松键。"""
        with self.lock:
            if self.active:
                self.on_pause(event)

    def resume(self, event: ContextEventItem | None = None) -> None:
        """仅向仍在执行的贝果操作转发恢复。"""
        with self.lock:
            if self.active:
                self.on_resume(event)

    def close(self) -> None:
        """等待已经开始的回调结束，并永久停用本次订阅。"""
        with self.lock:
            self.active = False


@contextmanager
def bagel_run_events(operation: Operation) -> Iterator[None]:
    """隔离贝果单次执行的回调，返回前等待回调结束并解除订阅。"""
    events = _BagelRunEvents(operation._on_pause, operation._on_resume)
    # 基类从这两个入口注册监听；独立订阅使旧队列事件不能影响下一次执行。
    operation._on_pause, operation._on_resume = events.pause, events.resume
    try:
        yield
    finally:
        events.close()
        try:
            operation.ctx.run_context.event_bus.unlisten_all_event(events)
            operation.ctx.run_context.event_bus.unlisten_all_event(operation)
        finally:
            operation._on_pause, operation._on_resume = events.on_pause, events.on_resume


class BagelOperation(ZOperation):
    """贝果操作失败时保存最后画面，便于核对停在哪一步。"""

    STATUS_DEFEATED: str = '贝果撤离失败'
    STATUS_INTERRUPTED: str = '贝果搜查或解锁被打断'

    def execute(self) -> OperationResult:
        """操作返回前完成贝果本次执行的事件清理。"""
        with bagel_run_events(self):
            return super().execute()

    def is_bagel_result(self) -> bool:
        """同时确认 DEFEAT 与高危雅努斯，不能仅凭单角色零血量退出。"""
        return (
            self.round_by_find_area(self.last_screenshot, '贝果-结算', '失败').is_success
            and expected_map(read_area(self.ctx, self.last_screenshot, '贝果-结算', '地图'))
        )

    def after_operation_done(self, result: OperationResult) -> None:
        """保存失败现场；截图写入异常不能阻止框架释放事件监听。"""
        try:
            if not result.success and self.last_screenshot is not None:
                path = self.save_screenshot()
                log.error('贝果操作停止：%s；现场截图：%s', result.status, path)
        except Exception:
            log.error('保存贝果失败截图时发生异常', exc_info=True)
        finally:
            self.ctx.run_context.event_bus.unlisten_all_event(self)
            super().after_operation_done(result)
