import cv2
import os
from typing import Optional, TYPE_CHECKING
from one_dragon.utils.log_utils import log
from cv2.typing import MatLike
from one_dragon.utils import cv2_utils
from zzz_od.application.inventory_scan.drive_disk.drive_disk_scan_app import DriveDiskScanApp
from zzz_od.application.inventory_scan.parser.wengine_parser import WengineParser
from zzz_od.application.inventory_scan.screenshot_cache import ScreenshotCache
from zzz_od.context.zzz_context import ZContext

if TYPE_CHECKING:
    from zzz_od.application.inventory_scan.ocr_worker import OcrWorker


class WengineScanApp(DriveDiskScanApp):

    def __init__(self, ctx: ZContext, screenshot_cache: Optional[ScreenshotCache] = None,
                 ocr_worker: Optional["OcrWorker"] = None):
        super().__init__(ctx, screenshot_cache=screenshot_cache, ocr_worker=ocr_worker)
        self.app_id = 'wengine_scan'
        self.op_name = '音擎扫描'
        self.parser = WengineParser()

    def _save_screenshot(self, row: int, col: int, screenshot: MatLike):
        """保存截图到缓存并提交OCR任务"""
        if self.screenshot_cache is None:
            return

        try:
            storage_area = self.ctx.screen_loader.get_area('仓库-驱动仓库', '驱动盘属性')
            cropped = cv2_utils.crop_image_only(screenshot, storage_area.rect)

            # 保存到音擎缓存（调试模式下会同时保存到文件）
            index = self.screenshot_cache.save('wengine', cropped)
            self.screenshot_index = index + 1

            # 提交OCR任务（异步处理）
            if self.ocr_worker is not None:
                self.ocr_worker.submit('wengine', cropped, self.parser)
        except Exception as e:
            log.error(f"保存截图失败({row+1},{col+1}): {e}")
