import threading
import queue
from typing import Optional, Any
from one_dragon.utils.log_utils import log
from cv2.typing import MatLike


class OcrWorker:
    """
    OCR工作线程，持续监控队列并处理OCR任务
    实现扫描和OCR的并行处理
    """

    def __init__(self, ctx: Any):
        """
        初始化OCR工作者

        Args:
            ctx: ZContext上下文，用于访问OCR服务
        """
        self.ctx = ctx
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()

        # 结果收集
        self.scanned_discs: list[dict] = []
        self.scanned_wengines: list[dict] = []
        self.scanned_agents: list[dict] = []

        # 统计信息
        self._processed_count = 0
        self._error_count = 0

    def start(self):
        """启动OCR工作线程"""
        self._stop_event.clear()
        self._processed_count = 0
        self._error_count = 0
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        log.debug("OCR工作线程已启动")

    def submit(self, task_type: str, screenshot: MatLike, parser: Any):
        """
        提交OCR任务

        Args:
            task_type: 任务类型 ('disc', 'wengine', 'agent')
            screenshot: 截图
            parser: 解析器实例
        """
        self._queue.put((task_type, screenshot, parser))

    def wait_complete(self):
        """等待所有任务完成"""
        self.resume()
        self._queue.join()
        log.debug(f"OCR处理完成: 成功{self._processed_count}个, 失败{self._error_count}个")

    def stop(self):
        """停止工作线程"""
        self.resume()
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        log.debug("OCR工作线程已停止")

    def pause(self):
        """暂停处理新任务（队列保留）"""
        self._pause_event.set()

    def resume(self):
        """恢复处理任务"""
        self._pause_event.clear()

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def reset(self):
        """重置结果收集"""
        self.scanned_discs.clear()
        self.scanned_wengines.clear()
        self.scanned_agents.clear()
        self._processed_count = 0
        self._error_count = 0

    def _worker(self):
        """工作线程主循环"""
        while not self._stop_event.is_set():
            try:
                if self._pause_event.is_set():
                    self._stop_event.wait(0.05)
                    continue

                task = self._queue.get(timeout=0.1)
                task_type, screenshot, parser = task

                try:
                    # OCR识别
                    ocr_result = self.ctx.ocr.run_ocr(screenshot)
                    if not ocr_result:
                        log.warning(f"OCR结果为空 ({task_type})")
                        self._error_count += 1
                        self._queue.task_done()
                        continue

                    # 转换OCR结果为解析器期望的格式
                    ocr_items = []
                    for text, match_list in ocr_result.items():
                        for match in match_list:
                            ocr_items.append({
                                'text': text,
                                'confidence': match.confidence if hasattr(match, 'confidence') else 1.0,
                                'position': (match.x, match.y, match.x + match.w, match.y + match.h) if hasattr(match, 'x') else None
                            })

                    # 解析数据
                    data = parser.parse_ocr_result(ocr_items, screenshot)
                    if data:
                        if task_type == 'disc':
                            self.scanned_discs.append(data)
                            log.debug(f"[OCR] 驱动盘解析成功: {data.get('setKey', 'unknown')}")
                        elif task_type == 'wengine':
                            self.scanned_wengines.append(data)
                            log.debug(f"[OCR] 音擎解析成功: {data.get('key', 'unknown')}")
                        elif task_type == 'agent':
                            self.scanned_agents.append(data)
                            log.debug(f"[OCR] 角色解析成功: {data.get('key', 'unknown')}")
                        self._processed_count += 1
                    else:
                        log.error(f"[OCR] 解析失败 ({task_type})")
                        self._error_count += 1

                except Exception as e:
                    log.error(f"[OCR] 处理任务失败 ({task_type}): {e}", exc_info=True)
                    self._error_count += 1

                self._queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                log.error(f"[OCR] 工作线程异常: {e}", exc_info=True)
