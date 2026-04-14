from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OverlayEventEnum(StrEnum):
    """Overlay module events published on ContextEventBus."""

    OVERLAY_LOG = "overlay_log"


@dataclass(slots=True)
class OverlayLogEvent:
    """Overlay log payload."""

    created: float
    level_name: str
    message: str
    filename: str
    lineno: int

