from dataclasses import dataclass

from PySide6.QtCore import QTimer

from one_dragon_qt.widgets.base_interface import BaseInterface


@dataclass(slots=True)
class _PreloadTask:
    interface: BaseInterface
    ctx: object
    retry_delay_ms: int
    cooldown_ms: int


_preload_queue: list[_PreloadTask] = []
_queue_started: bool = False
_queue_running: bool = False


def schedule_preload_after_context_ready(
    interface: BaseInterface,
    ctx: object,
    *,
    delay_ms: int,
    retry_delay_ms: int = 500,
    cooldown_ms: int = 1200,
) -> None:
    """在上下文就绪后按队列顺序预加载界面。"""
    global _queue_started

    _preload_queue.append(
        _PreloadTask(
            interface=interface,
            ctx=ctx,
            retry_delay_ms=retry_delay_ms,
            cooldown_ms=cooldown_ms,
        )
    )
    if _queue_started:
        return
    _queue_started = True
    QTimer.singleShot(delay_ms, _run_next_preload)


def _run_next_preload() -> None:
    global _queue_running

    if _queue_running or not _preload_queue:
        return

    task = _preload_queue[0]
    if not getattr(task.ctx, 'ready_for_application', True):
        QTimer.singleShot(task.retry_delay_ms, _run_next_preload)
        return

    _queue_running = True
    task.interface.preload_interface()
    _preload_queue.pop(0)
    _queue_running = False

    if _preload_queue:
        QTimer.singleShot(task.cooldown_ms, _run_next_preload)
