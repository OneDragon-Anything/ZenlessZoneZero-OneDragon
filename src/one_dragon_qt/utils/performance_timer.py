from __future__ import annotations

import logging
import time

from one_dragon.utils.log_utils import log


class UiPerformanceTimer:
    """UI 性能诊断计时器，仅在 DEBUG 日志级别输出。"""

    def __init__(
        self,
        name: str,
        *,
        threshold_ms: float = 0.0,
    ) -> None:
        self.name: str = name
        self.threshold_ms: float = threshold_ms
        self.enabled: bool = log.isEnabledFor(logging.DEBUG)
        self._start_time: float = time.perf_counter()
        self._last_time: float = self._start_time

    def lap(self, label: str) -> float:
        """记录距离上一个计时点的耗时。"""
        if not self.enabled:
            return 0.0

        now = time.perf_counter()
        elapsed_ms = (now - self._last_time) * 1000
        self._last_time = now
        self._log(label, elapsed_ms)
        return elapsed_ms

    def total(self, label: str = '总计') -> float:
        """记录距离计时器创建时的总耗时。"""
        if not self.enabled:
            return 0.0

        elapsed_ms = (time.perf_counter() - self._start_time) * 1000
        self._log(label, elapsed_ms)
        return elapsed_ms

    def _log(self, label: str, elapsed_ms: float) -> None:
        if elapsed_ms < self.threshold_ms:
            return
        log.debug('[UI计时] %s | %s: %.2f ms', self.name, label, elapsed_ms)
