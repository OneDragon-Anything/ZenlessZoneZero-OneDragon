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
<<<<<<< HEAD
from zzz_od.application.inventory_scan.inventory_scan_config import AgentScanOptionEnum
from zzz_od.application.inventory_scan.ocr_worker import OcrWorker
from zzz_od.application.inventory_scan.special_scan.special_scan_app import SpecialScanApp
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
import os
import json
import time
<<<<<<< HEAD
from zzz_od.application.inventory_scan.pre_scan.pre_scan_app import PreScanApp
from zzz_od.application.inventory_scan.translation.translation_updater import TranslationUpdater
import requests
=======
>>>>>>> 4a7c252d (feat: 添加仓库扫描功能及相关界面和配置)

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
<<<<<<< HEAD
<<<<<<< HEAD
        
        # 初始化并更新翻译字典
        # self._update_translation_dict()

    def _get_scan_agent_option(self) -> str:
        """获取扫描代理人选项（运行时从 context 获取最新值）"""
        return getattr(self.ctx, '_inventory_scan_agent_option', None)
    
    # def _update_translation_dict(self) -> None:
    #     """更新翻译字典"""
    #     try:
    #         updater = TranslationUpdater()
    #         if updater.update_if_needed():
    #             log.info("翻译字典更新成功")
    #         else:
    #             log.info("翻译字典无需更新")
    #     except Exception as e:
    #         log.error(f"更新翻译字典失败: {e}")

    @operation_node(name='返回大世界-普通',is_start_node=True)
=======
        #区域配置
        self.agent_unlocked_area = self.ctx.screen_loader.get_area('代理人-信息', '代理人-是否为已解锁')
        self.agent_name_area = self.ctx.screen_loader.get_area('代理人-信息', '代理人-名称')
        self.switch_next_agent_area = self.ctx.screen_loader.get_area('代理人-信息', '按钮-下一位代理人')
        self.agent_drive_1_area = self.ctx.screen_loader.get_area('代理人-装备', '分区1')
        self.agent_drive_2_area = self.ctx.screen_loader.get_area('代理人-装备', '分区2')
        self.agent_drive_3_area = self.ctx.screen_loader.get_area('代理人-装备', '分区3')
        self.agent_drive_4_area = self.ctx.screen_loader.get_area('代理人-装备', '分区4')
        self.agent_drive_5_area = self.ctx.screen_loader.get_area('代理人-装备', '分区5')
        self.agent_drive_6_area = self.ctx.screen_loader.get_area('代理人-装备', '分区6')
        #前端值获取
        self.scan_agent_option = getattr(self.ctx, '_inventory_scan_agent_option', None)
        #print(f"获取到的代理人扫描选项: {self.scan_agent_option}, 类型: {type(self.scan_agent_option)}")
        #最大迭代次数
        self.max_iterations = 100
=======
        
        # 初始化并更新翻译字典
        # self._update_translation_dict()
>>>>>>> a91a624d (feat: 优化代理人检查报告界面和库存扫描功能)

    def _get_scan_agent_option(self) -> str:
        """获取扫描代理人选项（运行时从 context 获取最新值）"""
        return getattr(self.ctx, '_inventory_scan_agent_option', None)
    
    # def _update_translation_dict(self) -> None:
    #     """更新翻译字典"""
    #     try:
    #         updater = TranslationUpdater()
    #         if updater.update_if_needed():
    #             log.info("翻译字典更新成功")
    #         else:
    #             log.info("翻译字典无需更新")
    #     except Exception as e:
    #         log.error(f"更新翻译字典失败: {e}")

    @operation_node(name='返回大世界-普通',is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        """返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())
    
    @node_from(from_name='返回大世界-普通')
    @operation_node(name='准备截图文件夹')
    def prepare_screenshots_dir(self) -> OperationRoundResult:
        """准备截图文件夹并启动OCR工作线程"""
        import shutil
        if os.path.exists(self.screenshots_dir):
            shutil.rmtree(self.screenshots_dir)
        self.ocr_worker.reset()
        self.ocr_worker.start()
        return self.round_success('截图文件夹已准备，且OCR工作线程已启动')
    
    
    
    @node_from(from_name='准备截图文件夹')
    @operation_node(name='预扫描')
    def pre_scan(self) -> OperationRoundResult:
        """预扫描"""
        scan_agent_option = self._get_scan_agent_option()
        #print(f'scan_agent_option: {scan_agent_option}')
        if scan_agent_option is None:
            return self.round_fail('扫描选项未设置')
        if scan_agent_option == AgentScanOptionEnum.UPDATE_AGENTS.value.value:
            # AgentScanOptionEnum.UPDATE_AGENTS.value 是 ConfigItem
            # .value 再次访问得到 ConfigItem.value，即字符串 '更新代理人列表'
            try:
                self.pre_scan_app = PreScanApp(self.ctx, self.ocr_worker)
                result = self.pre_scan_app.execute()
                if result.success:
                    return self.round_success('预扫描完成')
                else:
                    return self.round_fail('预扫描失败')
            except Exception as e:
                return self.round_fail(f'预扫描执行失败: {str(e)}')
        return self.round_success('跳过预扫描')

    @node_from('预扫描')
    @operation_node(name='扫描特定代理人')
    def scan_specific_agent(self) -> OperationRoundResult:
        """扫描特定代理人"""
        scan_agent_option = self._get_scan_agent_option()
        if scan_agent_option and scan_agent_option != AgentScanOptionEnum.UPDATE_AGENTS.value.value:
            try:
                self.special_scan_app = SpecialScanApp(self.ctx, self.ocr_worker)
                result = self.special_scan_app.execute()
                if result.success:
                    return self.round_success('特定扫描完成')
                else:
                    return self.round_fail('特定扫描失败')
            except Exception as e:
                return self.round_fail(f'特定扫描执行失败: {str(e)}')
        return self.round_success('跳过特定扫描')
            
