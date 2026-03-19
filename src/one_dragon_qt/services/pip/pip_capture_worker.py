import time
from collections.abc import Callable
from threading import Event

import numpy as np
from cv2.typing import MatLike
from PySide6.QtCore import QThread, Signal

from one_dragon.utils.log_utils import log


class PipCaptureWorker(QThread):
    """独立线程截图，通过信号将帧数据传递给主线程。"""

    frame_ready = Signal(np.ndarray)

    def __init__(
        self,
        capture_fn: Callable[[], MatLike | None],
        target_fps: int = 30,
    ) -> None:
        super().__init__()
        if target_fps <= 0:
            raise ValueError(f'target_fps must be > 0, got {target_fps}')
        self._capture_fn = capture_fn
        self._target_interval: float = 1.0 / target_fps
        self._running = Event()
        self._running.set()
        self._paused = Event()

    def run(self) -> None:
        while self._running.is_set():
            if self._paused.is_set():
                time.sleep(0.05)
                continue

            start = time.perf_counter()
            try:
                frame = self._capture_fn()
            except Exception:
                log.debug('画中画截图失败', exc_info=True)
                frame = None

            if frame is not None:
                self.frame_ready.emit(frame.copy())

            elapsed = time.perf_counter() - start
            sleep_time = self._target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def stop(self) -> None:
        self._running.clear()
        self._paused.clear()
        self.wait()
