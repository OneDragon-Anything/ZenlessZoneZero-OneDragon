from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from one_dragon.utils import os_utils
from zzz_od.application.inventory_scan import inventory_scan_const
from zzz_od.application.inventory_scan.inventory_scan_config import InventoryScanConfig
from zzz_od.application.inventory_scan.drive_disk.drive_disk_scan_app import DriveDiskScanApp
from zzz_od.application.inventory_scan.wengine.wengine_scan_app import WengineScanApp
from zzz_od.application.inventory_scan.agent.agent_scan_app import AgentScanApp
from zzz_od.application.inventory_scan.screenshot_cache import ScreenshotCache
from zzz_od.application.inventory_scan.ocr_worker import OcrWorker
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
import os


class InventoryScanApp(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=inventory_scan_const.APP_ID,
            op_name=inventory_scan_const.APP_NAME,
        )
        targets = getattr(ctx, "_inventory_scan_targets", None) or {}
        self._scan_drive_disk: bool = bool(targets.get("drive_disk", True))
        self._scan_wengine: bool = bool(targets.get("wengine", True))
        self._scan_agent: bool = bool(targets.get("agent", True))

        self.config: InventoryScanConfig = self.ctx.run_context.get_config(
            app_id=inventory_scan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        # 截图目录和缓存
        self.screenshots_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_screenshots')
        self.screenshot_cache = ScreenshotCache(save_dir=self.screenshots_dir, debug_mode=False)

        # OCR工作者（异步处理OCR任务）
        self.ocr_worker = OcrWorker(ctx)

        # 实例化三个子扫描应用，传入共享的截图缓存和OCR工作者
        self.drive_disk_scanner = DriveDiskScanApp(ctx, screenshot_cache=self.screenshot_cache, ocr_worker=self.ocr_worker)
        self.wengine_scanner = WengineScanApp(ctx, screenshot_cache=self.screenshot_cache, ocr_worker=self.ocr_worker)
        self.agent_scanner = AgentScanApp(ctx, screenshot_cache=self.screenshot_cache, ocr_worker=self.ocr_worker)

    @operation_node(name='开始前返回', is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        """返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='开始前返回')
    @operation_node(name='准备截图文件夹')
    def prepare_screenshots_dir(self) -> OperationRoundResult:
        """准备截图文件夹并启动OCR工作线程"""
        import shutil
        if os.path.exists(self.screenshots_dir):
            shutil.rmtree(self.screenshots_dir)
        # os.makedirs(self.screenshots_dir, exist_ok=True)
        # log.info(f"截图文件夹已准备: {self.screenshots_dir}")

        # 清空所有缓存并重置索引，确保从0开始
        self.screenshot_cache.reset_all()

        # 重置OCR工作者并启动
        self.ocr_worker.reset()
        self.ocr_worker.start()

        # 设置子扫描器的截图目录
        self.drive_disk_scanner.screenshots_dir = self.screenshots_dir
        self.wengine_scanner.screenshots_dir = self.screenshots_dir
        self.agent_scanner.screenshots_dir = self.screenshots_dir
        return self.round_success('截图文件夹已准备，OCR工作线程已启动')

    @node_from(from_name='准备截图文件夹')
    @operation_node(name='导航到驱动盘界面')
    def goto_drive_disk_screen(self) -> OperationRoundResult:
        """导航到驱动盘界面"""
        if not self._scan_drive_disk:
            return self.round_success('跳过驱动盘')
        return self.round_by_goto_screen(screen_name='仓库-驱动仓库')

    @node_from(from_name='导航到驱动盘界面')
    @operation_node(name='扫描驱动盘')
    def scan_drive_disks(self) -> OperationRoundResult:
        """扫描驱动盘"""
        if not self._scan_drive_disk:
            log.info("已跳过驱动盘扫描")
            return self.round_success('驱动盘已跳过')
        log.info("开始扫描驱动盘...")
        result = self.drive_disk_scanner.execute()
        if result.success:
            log.info("驱动盘扫描完成")
            return self.round_success('驱动盘扫描完成')
        else:
            log.error(f"驱动盘扫描失败: {result.status}")
            return self.round_fail(f'驱动盘扫描失败: {result.status}')

    @node_from(from_name='扫描驱动盘')
    @operation_node(name='导航到音擎界面')
    def goto_wengine_screen(self) -> OperationRoundResult:
        """导航到音擎界面"""
        if not self._scan_wengine:
            return self.round_success('跳过音擎')
        return self.round_by_goto_screen(screen_name='仓库-音擎仓库')

    @node_from(from_name='导航到音擎界面')
    @operation_node(name='扫描音擎')
    def scan_wengines(self) -> OperationRoundResult:
        """扫描音擎"""
        if not self._scan_wengine:
            log.info("已跳过音擎扫描")
            return self.round_success('音擎已跳过')
        log.info("开始扫描音擎...")
        result = self.wengine_scanner.execute()
        if result.success:
            log.info("音擎扫描完成")
            return self.round_success('音擎扫描完成')
        else:
            log.error(f"音擎扫描失败: {result.status}")
            return self.round_fail(f'音擎扫描失败: {result.status}')

    @node_from(from_name='扫描音擎')
    @operation_node(name='导航到代理人界面', node_max_retry_times=30)
    def goto_agent_screen(self) -> OperationRoundResult:
        """导航到代理人界面"""
        if not self._scan_agent:
            return self.round_success('跳过角色')

        nav_result = self.round_by_goto_screen(screen_name='代理人-信息')
        if not nav_result.is_success:
            return nav_result

        # 检测基础按钮是否彩色（加载完成）
        screen = self.screenshot()
        if self._is_button_colorful(screen, '代理人-信息', '按钮-代理人基础'):
            return self.round_success('已到达代理人界面')

        return self.round_retry(wait=0.1)

    def _is_button_colorful(self, screen, screen_name: str, area_name: str) -> bool:
        """
        检测按钮区域是否出现彩色（中间40%区域）
        """
        import cv2
        try:
            area = self.ctx.screen_loader.get_area(screen_name, area_name)

            x1, y1 = int(area.rect.x1), int(area.rect.y1)
            x2, y2 = int(area.rect.x2), int(area.rect.y2)
            region = screen[y1:y2, x1:x2]

            # 左右各裁剪30%，只检测中间40%
            width = region.shape[1]
            crop_left = int(width * 0.3)
            crop_right = int(width * 0.7)
            region = region[:, crop_left:crop_right]

            region_hsv = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)
            avg_s = float(region_hsv[:, :, 1].mean())

            return avg_s > 20
        except Exception:
            return False

    @node_from(from_name='导航到代理人界面')
    @operation_node(name='扫描角色')
    def scan_agents(self) -> OperationRoundResult:
        """扫描角色"""
        if not self._scan_agent:
            log.info("已跳过角色扫描")
            return self.round_success('角色已跳过')
        log.info("开始扫描角色...")
        result = self.agent_scanner.execute()
        if result.success:
            log.info("角色扫描完成")
            return self.round_success('角色扫描完成')
        else:
            log.error(f"角色扫描失败: {result.status}")
            return self.round_fail(f'角色扫描失败: {result.status}')

    @node_from(from_name='扫描角色')
    @operation_node(name='等待OCR完成')
    def wait_ocr_complete(self) -> OperationRoundResult:
        """等待OCR工作线程完成所有任务"""
        log.info("等待OCR处理完成...")

        # 等待所有OCR任务完成
        self.ocr_worker.wait_complete()

        # 停止工作线程
        self.ocr_worker.stop()

        # OCR完成后清空内存缓存，释放内存
        self.screenshot_cache.reset_all()
        log.info("OCR处理完成，已清空内存缓存")

        return self.round_success('OCR处理完成')

    @node_from(from_name='等待OCR完成')
    @operation_node(name='导出完整数据')
    def export_all_data(self) -> OperationRoundResult:
        """导出所有扫描数据到一个JSON文件"""
        import json
        import time

        try:
            export_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_exports')
            os.makedirs(export_dir, exist_ok=True)

            timestamp = int(time.time())
            export_path = os.path.join(export_dir, f'inventory_{timestamp}.json')

            # 从OCR工作者收集所有数据
            export_data = {
                'format': 'ZOD',
                'dbVersion': 2,
                'source': 'Zenless Optimizer',
                'version': 1,
                'discs': self.ocr_worker.scanned_discs,
                'wengines': self.ocr_worker.scanned_wengines,
                'characters': self.ocr_worker.scanned_agents
            }

            json_str = json.dumps(export_data, indent=2, ensure_ascii=False)

            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(json_str)

            log.info(f'已导出完整数据到: {export_path}')
            log.info(f'驱动盘: {len(export_data["discs"])}个, 音擎: {len(export_data["wengines"])}个, 角色: {len(export_data["characters"])}个')

            return self.round_success('完整数据已导出')

        except Exception as e:
            log.error(f'导出完整数据失败: {e}')
            return self.round_fail(f'导出失败: {e}')


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = InventoryScanApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
