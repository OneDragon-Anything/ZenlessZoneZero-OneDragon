from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen.screen_utils import FindAreaResultEnum, find_area_in_screen
from one_dragon.utils.log_utils import log
from one_dragon.utils import os_utils
from zzz_od.application.inventory_scan import inventory_scan_const
# from zzz_od.application.inventory_scan.inventory_scan_config import InventoryScanConfig
# from zzz_od.application.inventory_scan.drive_disk.drive_disk_scan_app import DriveDiskScanApp
# from zzz_od.application.inventory_scan.wengine.wengine_scan_app import WengineScanApp
# from zzz_od.application.inventory_scan.agent.agent_scan_app import AgentScanApp
# from zzz_od.application.inventory_scan.screenshot_cache import ScreenshotCache
from zzz_od.application.inventory_scan.inventory_scan_config import AgentScanOptionEnum
from zzz_od.application.inventory_scan.ocr_worker import OcrWorker
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
import os
import json
import time
from zzz_od.application.inventory_scan.pre_scan.pre_scan_app import PreScanApp

class InventoryScanApp(ZApplication):
    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=inventory_scan_const.APP_ID,
            op_name=inventory_scan_const.APP_NAME,
        )
        self.screenshots_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_screenshots')
        self.data_file_path = os_utils.get_path_under_work_dir('.debug', 'inventory_data')
        self.ocr_worker = OcrWorker(ctx)
        #区域配置
        self.agent_unlocked_area = self.ctx.screen_loader.get_area('代理人-信息', '代理人-是否为已解锁')
        self.agent_name_area = self.ctx.screen_loader.get_area('代理人-信息', '代理人-名称')
        self.switch_next_agent_area = self.ctx.screen_loader.get_area('代理人-信息', '按钮-下一位代理人')
        #前端值获取
        self.scan_agent_option = getattr(self.ctx, '_inventory_scan_agent_option', None)
        print(f"获取到的代理人扫描选项: {self.scan_agent_option}, 类型: {type(self.scan_agent_option)}")

    @operation_node(name='预扫描',is_start_node=True)
    def pre_scan(self) -> OperationRoundResult:
        """预扫描"""
        if self.scan_agent_option == AgentScanOptionEnum.UPDATE_AGENTS.value.value:
            # AgentScanOptionEnum.UPDATE_AGENTS.value 是 ConfigItem
            # .value 再次访问得到 ConfigItem.value，即字符串 '更新代理人列表'
            self.pre_scan_app = PreScanApp(self.ctx)
            result = self.pre_scan_app.execute()
            if result.success:
                return self.round_success('预扫描完成')
            else:
                return self.round_fail('预扫描失败')
        return self.round_success('跳过预扫描')
