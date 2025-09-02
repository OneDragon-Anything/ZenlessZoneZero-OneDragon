from __future__ import annotations

import threading
from functools import lru_cache
from typing import Optional

from zzz_od.context.zzz_context import ZContext


class AppContainer:
    """
    Very small service locator to host a singleton ZContext.
    Uses the current active instance instead of forcing instance 0.
    """

    _lock = threading.Lock()
    _ctx: Optional[ZContext] = None

    @classmethod
    def get_ctx(cls) -> ZContext:
        if cls._ctx is not None:
            return cls._ctx
        with cls._lock:
            if cls._ctx is None:
                ctx = ZContext()
                # Load configs and initialize minimal services.
                ctx.init_by_config()
                # Lazy OCR/model load remains on-demand
                cls._ctx = ctx
        return cls._ctx


@lru_cache(maxsize=1)
def get_ctx() -> ZContext:
    return AppContainer.get_ctx()
