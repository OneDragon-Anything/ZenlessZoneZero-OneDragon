from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from one_dragon_qt.overlay.overlay_events import OverlayEventEnum, OverlayLogEvent

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class OverlayLogHandler(logging.Handler):
    """Bridge logging records to ContextEventBus for overlay rendering."""

    # 战斗日志不进入 overlay 主日志：自动战斗的识别/操作细节刷屏，
    # 且战斗状态已由 STATE / DECISION 面板单独展示。
    # 路径包含 auto_battle（绝区零战斗逻辑）或 conditional_operation（条件操作框架）即过滤。
    _FILTER_PATH_PARTS = ("auto_battle", "conditional_operation")

    def __init__(self, ctx: OneDragonContext):
        super().__init__()
        self.ctx = ctx

    def _should_skip(self, record: logging.LogRecord) -> bool:
        path = record.pathname.replace("\\", "/")
        return any(part in path for part in self._FILTER_PATH_PARTS)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self._should_skip(record):
                return
            message = record.getMessage()
            if record.exc_info:
                if self.formatter:
                    exception_text = self.formatter.formatException(record.exc_info)
                else:
                    exception_text = logging.Formatter().formatException(record.exc_info)
                message = f"{message}\n{exception_text}"

            event = OverlayLogEvent(
                created=record.created,
                level_name=record.levelname,
                message=message,
                filename=record.filename,
                lineno=int(record.lineno),
            )
            self.ctx.dispatch_event(OverlayEventEnum.OVERLAY_LOG.value, event)
        except Exception:
            # Never raise from a logging handler.
            return
