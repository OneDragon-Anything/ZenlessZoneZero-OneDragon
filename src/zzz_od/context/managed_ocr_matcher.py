from __future__ import annotations

import threading
import time
from collections.abc import Callable

from cv2.typing import MatLike

from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher, OnnxOcrParam
from one_dragon.utils.log_utils import log


class ManagedOnnxOcrMatcher(OnnxOcrMatcher):
    """绝区零侧的 OCR 生命周期管理器。"""

    def __init__(
        self,
        ocr_param: OnnxOcrParam,
        idle_release_seconds: float = 30 * 60,
        release_check_interval: float = 60,
    ) -> None:
        super().__init__(ocr_param)
        self._lifecycle_lock: threading.RLock = threading.RLock()
        self._init_lock = self._lifecycle_lock
        self._idle_release_seconds: float = idle_release_seconds
        self._release_check_interval: float = release_check_interval
        self._last_used_at: float | None = None
        self._proxy_url: str | None = None
        self._ghproxy_url: str | None = None
        self._shutdown: bool = False
        self._shutdown_event: threading.Event = threading.Event()
        self._release_thread: threading.Thread | None = None

    def configure_runtime(
        self,
        use_gpu: bool,
        proxy_url: str | None,
        ghproxy_url: str | None,
    ) -> None:
        """更新 OCR 运行配置，不主动加载 ONNX 会话。"""
        with self._lifecycle_lock:
            self._proxy_url = proxy_url
            self._ghproxy_url = ghproxy_url
            if self._ocr_param.use_gpu == use_gpu:
                return

            self._ocr_param.use_gpu = use_gpu
            self._release_model_locked('OCR GPU 配置变更')

    def update_use_gpu(self, use_gpu: bool) -> None:
        """更新 GPU 开关，并释放已加载的旧会话。"""
        with self._lifecycle_lock:
            if self._ocr_param.use_gpu == use_gpu:
                return
            self._ocr_param.use_gpu = use_gpu
            self._release_model_locked('OCR GPU 配置变更')

    def init_model(
        self,
        download_by_github: bool = True,
        download_by_gitee: bool = False,
        download_by_mirror_chan: bool = False,
        proxy_url: str | None = None,
        ghproxy_url: str | None = None,
        skip_if_existed: bool = True,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> bool:
        """懒加载 OCR 模型，并启动空闲释放监控。"""
        with self._lifecycle_lock:
            if self._shutdown:
                log.warning('OCR 已关闭，跳过模型初始化')
                return False

            actual_proxy_url = proxy_url if proxy_url is not None else self._proxy_url
            actual_ghproxy_url = ghproxy_url if ghproxy_url is not None else self._ghproxy_url
            success = super().init_model(
                download_by_github=download_by_github,
                download_by_gitee=download_by_gitee,
                download_by_mirror_chan=download_by_mirror_chan,
                proxy_url=actual_proxy_url,
                ghproxy_url=actual_ghproxy_url,
                skip_if_existed=skip_if_existed,
                progress_callback=progress_callback,
            )
            if success:
                self._touch_locked()
                self._ensure_release_monitor_started_locked()
            return success

    def run_ocr_single_line(
        self,
        image: MatLike,
        threshold: float = 0,
        strict_one_line: bool = True,
    ) -> str:
        """单行 OCR，期间禁止释放模型。"""
        with self._lifecycle_lock:
            if self._shutdown:
                log.warning('OCR 已关闭，跳过单行识别')
                return ''

            try:
                return super().run_ocr_single_line(image, threshold, strict_one_line)
            finally:
                self._touch_locked()

    def run_ocr(
        self,
        image: MatLike,
        threshold: float | None = 0,
        merge_line_distance: float = -1,
    ) -> dict[str, MatchResultList]:
        """整图 OCR，期间禁止释放模型。"""
        with self._lifecycle_lock:
            if self._shutdown:
                log.warning('OCR 已关闭，跳过整图识别')
                return {}

            try:
                return super().run_ocr(image, threshold, merge_line_distance)
            finally:
                self._touch_locked()

    def ocr(
        self,
        image: MatLike,
        threshold: float = 0,
        merge_line_distance: float = -1,
    ) -> list[OcrMatchResult]:
        """OCR 列表接口，补齐业务侧懒加载保护。"""
        if image is None:
            log.warning('OCR输入的图片为None')
            return []

        with self._lifecycle_lock:
            if self._shutdown:
                log.warning('OCR 已关闭，跳过识别')
                return []

            try:
                if self._model is None and not self.init_model():
                    return []
                return super().ocr(image, threshold, merge_line_distance)
            finally:
                self._touch_locked()

    def release_idle_model(self, force: bool = False) -> bool:
        """释放超过空闲时间的 OCR 模型。"""
        with self._lifecycle_lock:
            if self._model is None:
                return False

            if not force:
                if self._last_used_at is None:
                    return False
                idle_seconds = time.monotonic() - self._last_used_at
                if idle_seconds < self._idle_release_seconds:
                    return False

            self._release_model_locked('OCR 空闲释放' if not force else 'OCR 强制释放')
            return True

    def shutdown(self) -> None:
        """停止空闲释放线程并释放模型。"""
        with self._lifecycle_lock:
            self._shutdown = True
            self._shutdown_event.set()
            release_thread = self._release_thread

        if release_thread is not None and release_thread.is_alive():
            if threading.current_thread() is not release_thread:
                release_thread.join(timeout=2)

        self.release_idle_model(force=True)

    def _touch_locked(self) -> None:
        """记录最近一次实际使用 OCR 模型的时间。"""
        if self._model is not None:
            self._last_used_at = time.monotonic()

    def _release_model_locked(self, reason: str) -> None:
        """在生命周期锁内释放 OCR 模型。"""
        if self._model is None:
            return

        model = self._model
        self._model = None
        self._last_used_at = None
        del model
        log.info(reason)

    def _ensure_release_monitor_started_locked(self) -> None:
        """确保空闲释放线程已启动。"""
        if self._shutdown:
            return

        if self._release_thread is not None and self._release_thread.is_alive():
            return

        self._shutdown_event.clear()
        self._release_thread = threading.Thread(
            target=self._release_monitor_loop,
            name='zzz_ocr_release_monitor',
            daemon=True,
        )
        self._release_thread.start()

    def _release_monitor_loop(self) -> None:
        """定期检查 OCR 模型是否需要空闲释放。"""
        while not self._shutdown_event.wait(self._release_check_interval):
            try:
                self.release_idle_model()
            except Exception:
                log.error('OCR 空闲释放检查失败', exc_info=True)
