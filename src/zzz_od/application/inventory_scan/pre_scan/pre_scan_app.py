from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen.screen_utils import FindAreaResultEnum, find_area_in_screen
from one_dragon.utils.log_utils import log
from one_dragon.utils import cv2_utils, os_utils
from zzz_od.application.inventory_scan.parser.agent_parser import AgentParser
from zzz_od.application.inventory_scan.parser.agent_name_parser import AgentNameParser
from zzz_od.application.inventory_scan.pre_scan import pre_scan_const
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

class PreScanApp(ZApplication):
    def __init__(self, ctx: ZContext, ocr_worker: OcrWorker):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=pre_scan_const.APP_ID,
            op_name=pre_scan_const.APP_NAME,
        )
        #配置工作线程及解析器
        self.ocr_worker = ocr_worker
        self.agent_name_parser = AgentNameParser()
        #配置路径
        self.screenshots_dir = os_utils.get_path_under_work_dir('.debug', 'inventory_screenshots')
        self.data_file_path = os_utils.get_path_under_work_dir('.debug', 'inventory_data')
        #区域配置
        self.agent_unlocked_area = self.ctx.screen_loader.get_area('代理人-信息', '代理人-是否为已解锁')
        self.agent_name_area = self.ctx.screen_loader.get_area('代理人-信息', '代理人-名称')
        self.switch_next_agent_area = self.ctx.screen_loader.get_area('代理人-信息', '按钮-下一位代理人')


    @operation_node(name='导航到代理人信息界面',is_start_node=True)
    def navigate_to_agent_info(self) -> OperationRoundResult:
        """导航到代理人信息界面"""
        return self.round_by_goto_screen(screen_name='代理人-信息')
    
    @node_from(from_name='导航到代理人信息界面')
    @operation_node(name='扫描代理人基础信息')
    def scan_agents(self) -> OperationRoundResult:
        """扫描代理人基础信息"""
        log.debug("开始扫描代理人基础信息...")
        time.sleep(1)# 等待代理人信息界面加载完成
        #遍历所有代理人
        max_iterations = 100  # 最大循环次数，避免无限循环
        iteration = 0
        agent_keys=[]
        while iteration < max_iterations:
            iteration += 1
            screen = self.screenshot()
            if screen is None:
                log.error("截图失败，无法获取屏幕画面")
                return self.round_fail('截图失败')
            result = find_area_in_screen(self.ctx, screen, self.agent_unlocked_area)
            if result == FindAreaResultEnum.TRUE:
                cropped_screen = cv2_utils.crop_image_only(screen, self.agent_name_area.rect)
                self.ocr_worker.submit('agent',cropped_screen,self.agent_name_parser)
                self.ctx.controller.click(self.switch_next_agent_area.rect.center)# 点击下一位代理人按钮
                time.sleep(0.3)# 等待下一位代理人加载完成

                # ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
                # image=screen,
                # rect=self.agent_name_area.rect,
                # color_range=self.agent_name_area.color_range,
                # crop_first=True
                # )
                # if ocr_result_list:
                #     agent_name=ocr_result_list[0].data
                #     agent_name_list.append(agent_name)
                #     print(f"代理人已解锁，名称为: {agent_name}")
                #     # 点击下一位代理人按钮
                #     self.ctx.controller.click(self.switch_next_agent_area.rect.center)
                #     time.sleep(0.3)# 等待下一位代理人加载完成
                # else:
                #     return self.round_fail('代理人名称扫描失败')
            else:
                log.info("代理人未解锁，结束扫描")
                break
        self.ocr_worker.wait_complete()
        agent_keys= [agent['key'] for agent in self.ocr_worker.scanned_agents]
        self.ocr_worker.reset()
        try:
            # 确保目录存在
            os.makedirs(self.data_file_path, exist_ok=True)
            # 使用 os.path.join 拼接路径
            json_file_path = os.path.join(self.data_file_path, 'agent_names.json')
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(agent_keys, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log.error(f"写代理人名称到JSON文件失败: {e}")
            return self.round_fail(f'写代理人名称到JSON文件失败: {e}')  
        return self.round_success('代理人扫描完成并写入JSON文件')  

    def execute(self) -> OperationResult:
        """执行预扫描"""
        try:
            result = super().execute()
            return result
        finally:
            self.ocr_worker.stop()