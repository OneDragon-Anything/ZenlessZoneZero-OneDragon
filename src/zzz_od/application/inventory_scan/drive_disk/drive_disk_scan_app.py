import cv2
import json
import os
import time
import shutil
from typing import Optional
from one_dragon.utils.log_utils import log

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, os_utils
from zzz_od.application.inventory_scan.drive_disk import drive_disk_scan_const
from zzz_od.application.inventory_scan.drive_disk.drive_disk_scan_config import DriveDiskScanConfig
from zzz_od.application.inventory_scan.parser.drive_disk_parser import DriveDiskParser
from zzz_od.application.inventory_scan.screenshot_cache import ScreenshotCache
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class DriveDiskScanApp(ZApplication):

    def __init__(self, ctx: ZContext, screenshot_cache: Optional[ScreenshotCache] = None):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=drive_disk_scan_const.APP_ID,
            op_name=drive_disk_scan_const.APP_NAME,
            node_max_retry_times=100000,
        )

        # 当前位置（行，列）从(0,0)开始，对应界面上的(1,1)
        self.current_row_idx: int = 0
        self.current_col_idx: int = 0

        # 网格信息（每次换行时更新）
        self.grid_rows: list[list[Point]] = []  # 二维网格
        self.total_scanned: int = 0  # 已扫描总数

        # 截图缓存
        self.screenshot_cache: Optional[ScreenshotCache] = screenshot_cache
        # 截图临时文件夹和序号
        self.screenshots_dir: Optional[str] = None
        self.screenshot_index: int = 0  # 全局递增序号

        # OCR处理标记
        self.ocr_processed: bool = False  # 防止重复OCR

        # 驱动盘属性解析器
        self.parser = DriveDiskParser()
        # 已扫描的驱动盘数据列表
        self.scanned_discs: list[dict] = []
        # 本次扫描的导出文件路径
        self.export_path: Optional[str] = None

    def execute(self) -> OperationResult:
        """执行扫描"""
        try:
            result = super().execute()
            return result
        finally:
            pass

    def _prepare_screenshots_dir(self):
        """准备截图临时文件夹"""
        base_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_screenshots')

        # 如果文件夹存在，清空
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)

        os.makedirs(base_dir, exist_ok=True)
        self.screenshots_dir = base_dir
        log.info(f"截图文件夹已准备: {self.screenshots_dir}")

    def _save_screenshot(self, row: int, col: int, screenshot: MatLike):
        """保存截图到缓存"""
        if self.screenshot_cache is None:
            return

        # 裁剪驱动盘仓库区域
        try:
            storage_area = self.ctx.screen_loader.get_area('仓库-驱动仓库', '驱动盘属性')
            cropped = cv2_utils.crop_image_only(screenshot, storage_area.rect)

            # 保存到驱动盘缓存（调试模式下会同时保存到文件）
            index = self.screenshot_cache.save('drive_disk', cropped)
            self.screenshot_index = index + 1
        except Exception as e:
            log.error(f"保存截图失败({row+1},{col+1}): {e}")

    def _batch_process_screenshots(self):
        """批量处理所有截图进行OCR"""
        # 防止重复执行
        if self.ocr_processed:
            log.info("OCR已处理完成，跳过重复执行")
            return

        self.ocr_processed = True

        if self.screenshot_cache is None:
            log.error("截图缓存未初始化")
            return

        # 获取所有驱动盘截图索引
        indices = self.screenshot_cache.get_all_indices('drive_disk')
        total_files = len(indices)

        if total_files == 0:
            log.warning("没有找到任何驱动盘截图")
            return

        log.info(f"找到{total_files}个驱动盘截图，开始OCR处理...")

        for idx, index in enumerate(indices, 1):
            try:
                # 从驱动盘缓存读取截图（先从内存读，没有再从文件读）
                screenshot = self.screenshot_cache.get('drive_disk', index)

                if screenshot is None:
                    log.error(f"读取截图失败(drive_disk-{index})")
                    continue

                # OCR处理
                self._process_screenshot_ocr(index, screenshot)

                # 进度日志（每10个输出一次）
                if idx % 10 == 0 or idx == total_files:
                    log.info(f"OCR进度: {idx}/{total_files} ({idx*100//total_files}%)")

            except Exception as e:
                log.error(f"处理截图异常(drive_disk-{index}): {e}")

        log.info(f"OCR处理完成，共识别{len(self.scanned_discs)}个驱动盘")

    def _process_screenshot_ocr(self, index: int, screenshot: MatLike):
        """处理单个截图的OCR"""
        try:
            # 直接OCR，不使用pipeline
            ocr_result = self.ctx.ocr.run_ocr(screenshot)

            if not ocr_result:
                log.warning(f"OCR结果为空(drive_disk-{index})")
                return

            # 转换OCR结果为列表
            ocr_items = []
            for text, match_list in ocr_result.items():
                for match in match_list:
                    ocr_items.append({
                        'text': text,
                        'confidence': match.confidence if hasattr(match, 'confidence') else 1.0,
                        'position': (match.x, match.y, match.x + match.w, match.y + match.h) if hasattr(match, 'x') else None
                    })

            # 解析并保存（传入screenshot和index用于异常保存）
            disc_data = self.parser.parse_ocr_result(ocr_items, screenshot=screenshot, index=index)
            if disc_data:
                self.scanned_discs.append(disc_data)
                log.info(f"识别成功(drive_disk-{index}): {disc_data.get('setKey', 'Unknown')} [{disc_data.get('slotKey', '?')}] Lv.{disc_data.get('level', 0)}")
            else:
                log.warning(f"解析失败(drive_disk-{index})")

        except Exception as e:
            log.error(f"OCR异常(drive_disk-{index}): {e}")

    @operation_node(name='初始化对齐', is_start_node=True)
    def initialize_align(self) -> OperationRoundResult:
        """开始前点击(1,1)确保坐标对齐"""
        screen = self.last_screenshot

        ctx = self.ctx.cv_service.run_pipeline('驱动盘方格', screen)
        if ctx.error_str is not None:
            return self.round_success(f'检测失败:{ctx.error_str}')

        if ctx.contours is None or len(ctx.contours) == 0:
            return self.round_success('未检测到方格')

        # 获取所有方格
        absolute_rects = ctx.get_absolute_rects()
        all_grids = []
        for x1, y1, x2, y2 in absolute_rects:
            center = Point(x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2)
            all_grids.append(center)

        # 网格化排序
        self.grid_rows = self._sort_grids(all_grids)

        if not self.grid_rows or len(self.grid_rows[0]) == 0:
            return self.round_success('网格为空')

        # 点击(1,1)确保对齐
        target = self.grid_rows[0][0]
        self.ctx.controller.click(target)

        return self.round_success(f'已对齐到(1,1) 检测到{len(self.grid_rows)}行')

    @node_from(from_name='初始化对齐')
    @node_from(from_name='扫描并点击下一格', status='换行')  # 换行后重新检测网格
    @node_from(from_name='扫描并点击下一格', status='滚动')  # 滚动后重新检测网格
    @operation_node(name='检测网格')
    def detect_grid(self) -> OperationRoundResult:
        """检测当前可见的驱动盘网格"""
        self.ctx.controller.mouse_move(Point(0, 0))  # 移动鼠标到(0,0)，避免遮挡方格
        time.sleep(0.02)  # 等待鼠标移动完成
        screen = self.screenshot()  # 重新截图，获取最新的网格布局

        ctx = self.ctx.cv_service.run_pipeline('驱动盘方格', screen)
        if ctx.error_str is not None:
            return self.round_success(f'检测失败:{ctx.error_str}')

        if ctx.contours is None or len(ctx.contours) == 0:
            return self.round_success('未检测到方格')

        # 获取所有方格的绝对坐标中心点
        absolute_rects = ctx.get_absolute_rects()
        all_grids = []
        for x1, y1, x2, y2 in absolute_rects:
            center = Point(x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2)
            all_grids.append(center)

        # 网格化排序
        self.grid_rows = self._sort_grids(all_grids)

        if not self.grid_rows:
            return self.round_success('网格为空')

        return self.round_success(f'检测到{len(self.grid_rows)}行 第1行{len(self.grid_rows[0])}列')

    @node_from(from_name='检测网格')
    @node_from(from_name='扫描并点击下一格', status='扫描中')  # 自循环：同行连续点击
    @node_from(from_name='扫描并点击下一格', status='最后一行 从(4,2)开始')  # 自循环：最后一行
    @operation_node(name='扫描并点击下一格')
    def scan_and_click_next(self) -> OperationRoundResult:
        """扫描当前格并点击下一格"""
        if not self.grid_rows:
            return self.round_fail('网格未初始化')

        # 检查是否超出范围
        if self.current_row_idx >= len(self.grid_rows):
            # 扫描完成
            log.info("驱动盘扫描完成")
            return self.round_success('扫描完成')

        current_row = self.grid_rows[self.current_row_idx]
        if self.current_col_idx >= len(current_row):
            # 当前行结束
            log.info("驱动盘扫描完成")
            return self.round_success('扫描完成')

        # 保存当前截图到文件
        current_screenshot = self.last_screenshot.copy()
        self._save_screenshot(self.current_row_idx, self.current_col_idx, current_screenshot)

        # 计算下一个位置
        next_row = self.current_row_idx
        next_col = self.current_col_idx + 1

        # 检查是否需要换行
        if next_col >= len(current_row):
            next_row += 1
            next_col = 0

            # 第4行第1个(索引3,0)：需要特殊处理
            if next_row == 3 and next_col == 0:
                # 点击(3,2)前检测进度条，判断是否已是最后一行
                ctx = self.ctx.cv_service.run_pipeline('驱动盘进度条检测', self.last_screenshot)
                has_progress_bar = ctx.contours is not None and len(ctx.contours) > 0

                if has_progress_bar:
                    # 有进度条：第3行就是最后一行，直接从(4,2)开始
                    if len(self.grid_rows) > 3 and len(self.grid_rows[3]) > 1:
                        target = self.grid_rows[3][1]  # 点击(4,2)
                        log.info(f"[点击] 检测到进度条，点击(3,1)")
                        self.ctx.controller.click(target)
                        self.current_row_idx = 3  # 第4行（索引3）
                        self.current_col_idx = 1  # 第2列（索引1）
                        self.total_scanned += 1
                        return self.round_success('最后一行 从(4,2)开始')
                    else:
                        # 扫描完成，开始OCR
                        log.info("点击完成，开始批量OCR处理...")
                        return self.round_success('扫描完成')
                else:
                    # 无进度条：点击(4,1)触发滚动
                    if len(self.grid_rows) > 3 and len(self.grid_rows[3]) > 0:
                        target = self.grid_rows[3][0]
                        log.info(f"[点击] 无进度条，点击(3,0)触发滚动")
                        self.ctx.controller.click(target)
                        self.total_scanned += 1
                        # 设置为(2,0)，下次循环会+1变成(2,1)
                        self.current_row_idx = 2  # 第3行（索引2）
                        self.current_col_idx = 0  # 第1列（索引0）
                        return self.round_success('滚动', wait=0.4)  # 等待滚动
                    else:
                        # 扫描完成，开始OCR
                        log.info("点击完成，开始批量OCR处理...")
                        return self.round_success('扫描完成')

            # 普通换行（不等待）
            if next_row < len(self.grid_rows):
                if len(self.grid_rows[next_row]) > 0:
                    target = self.grid_rows[next_row][0]
                    log.info(f"[点击] 换行，点击({next_row},{next_col})")
                    self.ctx.controller.click(target)
                    self.current_row_idx = next_row
                    self.current_col_idx = next_col
                    self.total_scanned += 1
                    return self.round_success('换行')  # 重新检测网格
            else:
                # 扫描完成
                log.info("驱动盘扫描完成")
                return self.round_success('扫描完成')

        # 同行点击下一个（不需要额外等待）
        target = current_row[next_col]
        log.info(f"[点击] 同行，点击({next_row},{next_col},{target})")
        self.ctx.controller.click(target)
        self.current_row_idx = next_row
        self.current_col_idx = next_col
        self.total_scanned += 1

        return self.round_success('扫描中', wait=0.02)

    def _sort_grids(self, all_disks: list[Point]) -> list[list[Point]]:
        """将所有方格整理为二维网格"""
        if not all_disks:
            return []

        # 按 y 坐标排序
        sorted_by_y = sorted(all_disks, key=lambda d: d.y)

        rows = []
        current_row = [sorted_by_y[0]]
        y_tolerance = 50

        for i in range(1, len(sorted_by_y)):
            disk = sorted_by_y[i]
            if abs(disk.y - current_row[0].y) <= y_tolerance:
                current_row.append(disk)
            else:
                current_row.sort(key=lambda d: d.x)
                rows.append(current_row)
                current_row = [disk]

        if current_row:
            current_row.sort(key=lambda d: d.x)
            rows.append(current_row)

        return rows

    def on_pause(self):
        """暂停"""
        super().on_pause()

    def on_resume(self):
        """恢复"""
        super().on_resume()

    def after_operation_done(self, result: OperationResult):
        """扫描完成后的清理工作"""
        # 最终导出
        if self.scanned_discs:
            self._export_scanned_discs()
            log.info(f"扫描完成，共识别{len(self.scanned_discs)}个驱动盘")

        ZApplication.after_operation_done(self, result)

    def _export_scanned_discs(self):
        """导出已扫描的驱动盘数据为JSON文件"""
        try:
            # 第一次导出时创建文件路径
            if self.export_path is None:
                export_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_exports')
                os.makedirs(export_dir, exist_ok=True)

                timestamp = int(time.time())
                self.export_path = os.path.join(export_dir, f'drive_disks_{timestamp}.json')

            # 生成JSON
            json_str = self.parser.generate_export_json(self.scanned_discs)

            # 保存到文件
            with open(self.export_path, 'w', encoding='utf-8') as f:
                f.write(json_str)

            log.info(f'已导出{len(self.scanned_discs)}个驱动盘数据到: {self.export_path}')

        except Exception as e:
            log.error(f'导出驱动盘数据失败: {e}')


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = DriveDiskScanApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()