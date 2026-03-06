from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from one_dragon_qt.overlay.overlay_events import OverlayEventEnum, OverlayLogEvent

if TYPE_CHECKING:
    from one_dragon.base.operation.one_dragon_context import OneDragonContext


class OverlayLogHandler(logging.Handler):
    """Bridge logging records to ContextEventBus for overlay rendering."""

    def __init__(self, ctx: "OneDragonContext"):
        super().__init__()
        self.ctx = ctx

    def emit(self, record: logging.LogRecord) -> None:
        try:
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

