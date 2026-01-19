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
        self.config: InventoryScanConfig = self.ctx.run_context.get_config(
            app_id=inventory_scan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        # 截图目录和缓存
        self.screenshots_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_screenshots')
        self.screenshot_cache = ScreenshotCache(save_dir=self.screenshots_dir, debug_mode=False)

        # 实例化三个子扫描应用，传入共享的截图缓存
        self.drive_disk_scanner = DriveDiskScanApp(ctx, screenshot_cache=self.screenshot_cache)
        self.wengine_scanner = WengineScanApp(ctx, screenshot_cache=self.screenshot_cache)
        self.agent_scanner = AgentScanApp(ctx, screenshot_cache=self.screenshot_cache)

    @operation_node(name='开始前返回', is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        """返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='开始前返回')
    @operation_node(name='准备截图文件夹')
    def prepare_screenshots_dir(self) -> OperationRoundResult:
        """准备截图文件夹"""
        import shutil
        if os.path.exists(self.screenshots_dir):
            shutil.rmtree(self.screenshots_dir)
        # os.makedirs(self.screenshots_dir, exist_ok=True)
        # log.info(f"截图文件夹已准备: {self.screenshots_dir}")

        # 清空所有缓存并重置索引，确保从0开始
        self.screenshot_cache.reset_all()

        # 设置子扫描器的截图目录
        self.drive_disk_scanner.screenshots_dir = self.screenshots_dir
        self.wengine_scanner.screenshots_dir = self.screenshots_dir
        self.agent_scanner.screenshots_dir = self.screenshots_dir
        return self.round_success('截图文件夹已准备')

    @node_from(from_name='准备截图文件夹')
    @operation_node(name='导航到驱动盘界面')
    def goto_drive_disk_screen(self) -> OperationRoundResult:
        """导航到驱动盘界面"""
        return self.round_by_goto_screen(screen_name='仓库-驱动仓库')

    @node_from(from_name='导航到驱动盘界面')
    @operation_node(name='扫描驱动盘')
    def scan_drive_disks(self) -> OperationRoundResult:
        """扫描驱动盘"""
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
        return self.round_by_goto_screen(screen_name='仓库-音擎仓库')

    @node_from(from_name='导航到音擎界面')
    @operation_node(name='扫描音擎')
    def scan_wengines(self) -> OperationRoundResult:
        """扫描音擎"""
        log.info("开始扫描音擎...")
        result = self.wengine_scanner.execute()
        if result.success:
            log.info("音擎扫描完成")
            return self.round_success('音擎扫描完成')
        else:
            log.error(f"音擎扫描失败: {result.status}")
            return self.round_fail(f'音擎扫描失败: {result.status}')

    @node_from(from_name='扫描音擎')
    @operation_node(name='导航到代理人界面')
    def goto_agent_screen(self) -> OperationRoundResult:
        """导航到代理人界面"""
        return self.round_by_goto_screen(screen_name='代理人-信息')

    @node_from(from_name='导航到代理人界面')
    @operation_node(name='扫描角色')
    def scan_agents(self) -> OperationRoundResult:
        """扫描角色"""
        log.info("开始扫描角色...")
        result = self.agent_scanner.execute()
        if result.success:
            log.info("角色扫描完成")
            return self.round_success('角色扫描完成')
        else:
            log.error(f"角色扫描失败: {result.status}")
            return self.round_fail(f'角色扫描失败: {result.status}')

    @node_from(from_name='扫描角色')
    @operation_node(name='批量OCR处理')
    def batch_ocr_process(self) -> OperationRoundResult:
        """批量OCR处理所有截图"""
        log.info("开始批量OCR处理...")

        # 调用驱动盘扫描器的OCR处理
        self.drive_disk_scanner._batch_process_screenshots()

        # 调用音擎扫描器的OCR处理
        self.wengine_scanner._batch_process_screenshots()

        # 调用代理人扫描器的OCR处理
        self.agent_scanner._batch_process_screenshots()

        # OCR完成后清空内存缓存，释放内存
        self.screenshot_cache.reset_all()
        log.info("批量OCR处理完成，已清空内存缓存")
        
        return self.round_success('批量OCR处理完成')

    @node_from(from_name='批量OCR处理')
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

            # 收集所有数据
            export_data = {
                'format': 'ZOD',
                'dbVersion': 2,
                'source': 'Zenless Optimizer',
                'version': 1,
                'discs': self.drive_disk_scanner.scanned_discs,
                'wengines': self.wengine_scanner.scanned_wengines,
                'characters': self.agent_scanner.scanned_agents if hasattr(self.agent_scanner, 'scanned_agents') else []
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

    @node_from(from_name='导出完整数据')
    @operation_node(name='完成后返回')
    def back_at_last(self) -> OperationRoundResult:
        """完成后返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = InventoryScanApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
