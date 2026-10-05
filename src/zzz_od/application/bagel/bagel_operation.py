from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation import Operation
from one_dragon.utils.log_utils import log
from zzz_od.application.bagel.bagel_screen import expected_map, read_area
from zzz_od.operation.zzz_operation import ZOperation

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from one_dragon.base.operation.context_event_bus import ContextEventItem
    from one_dragon.base.operation.operation_base import OperationResult
    from one_dragon.base.operation.operation_round_result import OperationRoundResult


def is_bagel_result(operation: Operation) -> bool:
    """用失败标志和高危雅努斯标题共同核对结算，供应用与操作复用。"""
    return (
        operation.round_by_find_area(operation.last_screenshot, '贝果-结算', '失败').is_success
        and expected_map(read_area(operation.ctx, operation.last_screenshot, '贝果-结算', '地图'))
    )


def execute_bagel_round(operation: Operation) -> OperationRoundResult:
    """贝果程序异常直接停止，避免框架重试把错误改写为业务超时。"""
    try:
        return Operation._execute_one_round(operation)
    except Exception as error:
        log.error('贝果节点执行异常，停止并保留现场', exc_info=True)
        return operation.round_fail('异常', data=f'{type(error).__name__}：{error}')


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


@dataclass(frozen=True)
class BagelRecoverableFailure:
    """明确可结算重开的业务失败；框架异常不会产生此标记。"""

    reason: str


class BagelOperation(ZOperation):
    """贝果操作失败时保存最后画面，便于核对停在哪一步。"""

    STATUS_DEFEATED: str = '贝果撤离失败'
    STATUS_INTERRUPTED: str = '贝果搜查或解锁被打断'
    STATUS_CLEANUP_FAILED: str = '贝果收尾失败'
    STATUS_ROUND_FAILED: str = '贝果局内流程失败'
    STATUS_CONTAINER_FAILED: str = '贝果容器靠近或开箱恢复失败'

    def _execute_one_round(self) -> OperationRoundResult:
        """程序异常不在局内继续重试输入。"""
        return execute_bagel_round(self)

    def round_recoverable_fail(self, reason: str) -> OperationRoundResult:
        """保留原始状态，并供正式应用区分业务失败与程序错误。"""
        return self.round_fail(reason, data=BagelRecoverableFailure(reason))

    def _has(self, area: str, screen_name: str = '贝果-局内') -> bool:
        """只使用当前截图核对指定画面区域。"""
        return self.round_by_find_area(self.last_screenshot, screen_name, area).is_success

    def execute(self) -> OperationResult:
        """操作返回前完成贝果本次执行的事件清理。"""
        with bagel_run_events(self):
            return super().execute()

    def is_bagel_result(self) -> bool:
        """同时确认 DEFEAT 与高危雅努斯，不能仅凭单角色零血量退出。"""
        return is_bagel_result(self)

    def after_operation_done(self, result: OperationResult) -> None:
        """保存失败现场；截图写入异常不能阻止框架释放事件监听。"""
        try:
            if not result.success and self.last_screenshot is not None:
                path = self.save_screenshot()
                log.error(f'贝果操作停止：{result.status}；原因：{result.data}；现场截图：{path}')
        except Exception:
            log.error('保存贝果失败截图时发生异常', exc_info=True)
        finally:
            self.ctx.run_context.event_bus.unlisten_all_event(self)
            super().after_operation_done(result)
