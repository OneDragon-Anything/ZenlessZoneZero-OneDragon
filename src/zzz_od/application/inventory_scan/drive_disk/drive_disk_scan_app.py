import cv2
import json
import os
import time
import shutil
from typing import Optional, TYPE_CHECKING
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

if TYPE_CHECKING:
    from zzz_od.application.inventory_scan.ocr_worker import OcrWorker


class DriveDiskScanApp(ZApplication):

    def __init__(self, ctx: ZContext, screenshot_cache: Optional[ScreenshotCache] = None,
                 ocr_worker: Optional["OcrWorker"] = None):
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
        self.ocr_worker = ocr_worker
        # 截图临时文件夹和序号
        self.screenshots_dir: Optional[str] = None
        self.screenshot_index: int = 0  # 全局递增序号

        # OCR处理标记
        self.ocr_processed: bool = False  # 防止重复OCR

        # 驱动盘属性解析器
        self.parser = DriveDiskParser()
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
        """保存截图到缓存并提交OCR任务"""
        if self.screenshot_cache is None:
            return

        # 裁剪驱动盘仓库区域
        try:
            storage_area = self.ctx.screen_loader.get_area('仓库-驱动仓库', '驱动盘属性')
            cropped = cv2_utils.crop_image_only(screenshot, storage_area.rect)

            # 保存到驱动盘缓存（调试模式下会同时保存到文件）
            index = self.screenshot_cache.save('drive_disk', cropped)
            self.screenshot_index = index + 1

            # 提交OCR任务（异步处理）
            if self.ocr_worker is not None:
                self.ocr_worker.submit('disc', cropped, self.parser)
        except Exception as e:
            log.error(f"保存截图失败({row+1},{col+1}): {e}")

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
    @node_from(from_name='扫描当前行', status='换行')  # 换行后重新检测网格
    @node_from(from_name='扫描当前行', status='滚动')  # 滚动后重新检测网格
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
    @node_from(from_name='扫描当前行', status='换行')  # 换行后继续扫描
    @node_from(from_name='扫描当前行', status='最后一行')  # 最后一行继续扫描
    @operation_node(name='扫描当前行')
    def scan_current_row(self) -> OperationRoundResult:
        """扫描当前行的所有格子（内部循环，不经过状态机）"""
        if not self.grid_rows:
            return self.round_fail('网格未初始化')

        # 检查是否超出范围
        if self.current_row_idx >= len(self.grid_rows):
            log.info("驱动盘扫描完成")
            return self.round_success('扫描完成')

        current_row = self.grid_rows[self.current_row_idx]
        if self.current_col_idx >= len(current_row):
            log.info("驱动盘扫描完成")
            return self.round_success('扫描完成')

        # 同行内循环点击，不经过状态机
        while self.current_col_idx < len(current_row):
            # 保存当前截图
            current_screenshot = self.last_screenshot.copy()
            self._save_screenshot(self.current_row_idx, self.current_col_idx, current_screenshot)
            self.total_scanned += 1

            # 计算下一个位置
            next_col = self.current_col_idx + 1

            # 检查是否到达行尾
            if next_col >= len(current_row):
                # 行尾，需要换行处理
                break

            # 同行点击下一个
            target = current_row[next_col]
            log.info(f"[点击] 同行，点击({self.current_row_idx},{next_col})")
            self.ctx.controller.click(target)
            self.current_col_idx = next_col

            # 等待画面更新后重新截图
            self.screenshot()

        # 行结束，处理换行逻辑
        next_row = self.current_row_idx + 1
        next_col = 0

        # 第4行第1个(索引3,0)：需要特殊处理
        if next_row == 3 and next_col == 0:
            ctx = self.ctx.cv_service.run_pipeline('驱动盘进度条检测', self.last_screenshot)
            has_progress_bar = ctx.contours is not None and len(ctx.contours) > 0

            if has_progress_bar:
                # 有进度条：第4行是最后一行
                if len(self.grid_rows) > 3 and len(self.grid_rows[3]) > 0:
                    target = self.grid_rows[3][0]
                    log.info(f"[点击] 检测到进度条，点击(3,0)进入最后一行")
                    self.ctx.controller.click(target)
                    self.current_row_idx = 3
                    self.current_col_idx = 0
                    return self.round_success('最后一行')
                else:
                    log.info("点击完成，扫描结束")
                    return self.round_success('扫描完成')
            else:
                # 无进度条：点击(4,1)触发滚动
                if len(self.grid_rows) > 3 and len(self.grid_rows[3]) > 0:
                    target = self.grid_rows[3][0]
                    log.info(f"[点击] 无进度条，点击(3,0)触发滚动")
                    self.ctx.controller.click(target)
                    self.current_row_idx = 2
                    self.current_col_idx = 0
                    return self.round_success('滚动', wait=0.4)
                else:
                    log.info("点击完成，扫描结束")
                    return self.round_success('扫描完成')

        # 普通换行
        if next_row < len(self.grid_rows):
            if len(self.grid_rows[next_row]) > 0:
                target = self.grid_rows[next_row][0]
                log.info(f"[点击] 换行，点击({next_row},{next_col})")
                self.ctx.controller.click(target)
                self.current_row_idx = next_row
                self.current_col_idx = next_col
                return self.round_success('换行')

        log.info("驱动盘扫描完成")
        return self.round_success('扫描完成')

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


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = DriveDiskScanApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()