import time
from collections.abc import Callable

import numpy as np
from cv2.typing import MatLike
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from one_dragon.utils.log_utils import log


class PipCaptureWorker(QThread):
    """独立线程截图，通过信号将 QImage 传递给主线程。"""

    frame_ready = Signal(QImage)

    def __init__(
        self,
        capture_fn: Callable[[], MatLike | None],
        target_fps: int = 30,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._capture_fn = capture_fn
        self._target_interval: float = 1.0 / target_fps
        self._running: bool = True

    def run(self) -> None:
        while self._running:
            start = time.perf_counter()
            try:
                frame = self._capture_fn()
            except Exception:
                log.debug('画中画截图失败', exc_info=True)
                frame = None

            if frame is not None:
                q_image = self._numpy_to_qimage(frame)
                if q_image is not None:
                    self.frame_ready.emit(q_image)

            elapsed = time.perf_counter() - start
            sleep_time = self._target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self) -> None:
        self._running = False
        self.wait()

    @staticmethod
    def _numpy_to_qimage(image: np.ndarray) -> QImage | None:
        """将 RGB numpy 数组转换为 QImage (线程安全)"""
        if image.ndim != 3 or image.shape[2] != 3:
            return None
        if image.dtype != np.uint8:
            image = image.astype(np.uint8)
        if not image.flags['C_CONTIGUOUS']:
            image = np.ascontiguousarray(image)
        h, w, _ = image.shape
        q_image = QImage(image.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        return q_image.copy()
