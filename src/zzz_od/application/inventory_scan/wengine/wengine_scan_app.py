import cv2
import os
from typing import Optional
from one_dragon.utils.log_utils import log
from cv2.typing import MatLike
from one_dragon.utils import cv2_utils
from zzz_od.application.inventory_scan.drive_disk.drive_disk_scan_app import DriveDiskScanApp
from zzz_od.application.inventory_scan.parser.wengine_parser import WengineParser
from zzz_od.application.inventory_scan.screenshot_cache import ScreenshotCache
from zzz_od.context.zzz_context import ZContext


class WengineScanApp(DriveDiskScanApp):

    def __init__(self, ctx: ZContext, screenshot_cache: Optional[ScreenshotCache] = None):
        super().__init__(ctx, screenshot_cache=screenshot_cache)
        self.app_id = 'wengine_scan'
        self.op_name = '音擎扫描'
        self.parser = WengineParser()
        self.scanned_wengines: list[dict] = []

    def _save_screenshot(self, row: int, col: int, screenshot: MatLike):
        """保存截图到缓存"""
        if self.screenshot_cache is None:
            return

        try:
            storage_area = self.ctx.screen_loader.get_area('仓库-驱动仓库', '驱动盘属性')
            cropped = cv2_utils.crop_image_only(screenshot, storage_area.rect)

            # 保存到音擎缓存（调试模式下会同时保存到文件）
            index = self.screenshot_cache.save('wengine', cropped)
            self.screenshot_index = index + 1
        except Exception as e:
            log.error(f"保存截图失败({row+1},{col+1}): {e}")

    def _batch_process_screenshots(self):
        """批量处理所有截图进行OCR"""
        if self.ocr_processed:
            log.info("OCR已处理完成，跳过重复执行")
            return

        self.ocr_processed = True

        if self.screenshot_cache is None:
            log.error("截图缓存未初始化")
            return

        # 获取所有音擎截图索引
        indices = self.screenshot_cache.get_all_indices('wengine')
        total_files = len(indices)

        if total_files == 0:
            log.warning("没有找到任何音擎截图")
            return

        log.info(f"找到{total_files}个音擎截图，开始OCR处理...")

        for idx, index in enumerate(indices, 1):
            try:
                # 从音擎缓存读取截图（先从内存读，没有再从文件读）
                screenshot = self.screenshot_cache.get('wengine', index)

                if screenshot is None:
                    log.error(f"读取截图失败(wengine-{index})")
                    continue

                self._process_screenshot_ocr(index, screenshot)

                if idx % 10 == 0 or idx == total_files:
                    log.info(f"OCR进度: {idx}/{total_files} ({idx*100//total_files}%)")

            except Exception as e:
                log.error(f"处理截图异常(wengine-{index}): {e}")

        log.info(f"OCR处理完成，共识别{len(self.scanned_wengines)}个音擎")

    def _process_screenshot_ocr(self, index: int, screenshot: MatLike):
        """处理单个截图的OCR"""
        try:
            ocr_result = self.ctx.ocr.run_ocr(screenshot)

            if not ocr_result:
                log.warning(f"OCR结果为空(wengine-{index})")
                return

            ocr_items = []
            for text, match_list in ocr_result.items():
                for match in match_list:
                    ocr_items.append({
                        'text': text,
                        'confidence': match.confidence if hasattr(match, 'confidence') else 1.0,
                        'position': (match.x, match.y, match.x + match.w, match.y + match.h) if hasattr(match, 'x') else None
                    })

            wengine_data = self.parser.parse_ocr_result(ocr_items, screenshot)
            if wengine_data:
                self.scanned_wengines.append(wengine_data)
                log.info(f"识别成功(wengine-{index}): {wengine_data.get('key', 'Unknown')} Lv.{wengine_data.get('level', 0)} 精炼{wengine_data.get('modification', 0)} 突破{wengine_data.get('promotion', 0)}")
            else:
                log.warning(f"解析失败(wengine-{index})")

        except Exception as e:
            log.error(f"OCR异常(wengine-{index}): {e}")

    def after_operation_done(self, result):
        """扫描完成后的清理工作"""
        if self.scanned_wengines:
            self._export_scanned_wengines()
            log.info(f"音擎扫描完成，共识别{len(self.scanned_wengines)}个")
        super(DriveDiskScanApp, self).after_operation_done(result)

    def _export_scanned_wengines(self):
        """导出已扫描的音擎数据为JSON文件"""
        try:
            import time
            from one_dragon.utils import os_utils

            export_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_exports')
            os.makedirs(export_dir, exist_ok=True)

            timestamp = int(time.time())
            export_path = os.path.join(export_dir, f'wengines_{timestamp}.json')

            json_str = self.parser.generate_export_json(self.scanned_wengines)

            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(json_str)

            log.info(f'已导出{len(self.scanned_wengines)}个音擎数据到: {export_path}')

        except Exception as e:
            log.error(f'导出音擎数据失败: {e}')
