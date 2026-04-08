import json
import os
import time
import cv2
import numpy as np
from one_dragon.utils.log_utils import log
from zzz_od.application.inventory_scan.parser.wengine_parser import WengineParser
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.application.inventory_scan.special_scan import special_scan_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from one_dragon.base.screen.screen_utils import FindAreaResultEnum, find_area_in_screen
from zzz_od.application.inventory_scan.ocr_worker import OcrWorker
from zzz_od.application.inventory_scan.parser.drive_disk_parser import DriveDiskParser
from zzz_od.application.inventory_scan.parser.agent_parser import AgentParser
from one_dragon.utils import cv2_utils, os_utils
from zzz_od.application.inventory_scan.parser.agent_name_parser import AgentNameParser

class SpecialScanApp(ZApplication):
    def __init__(self, ctx: ZContext,ocr_worker: OcrWorker):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=special_scan_const.APP_ID,
            op_name=special_scan_const.APP_NAME,
        )
        self.ocr_worker = ocr_worker
        self.agent_name_parser = AgentNameParser()
        self.agent_parser = AgentParser()
        self.drive_disk_parser = DriveDiskParser()
        self.wengine_parser = WengineParser()
        
        #配置文件路径
        self.data_file_path = os_utils.get_path_under_work_dir('.debug', 'inventory_data')
        # 区域配置
        self.agent_name_area = self.ctx.screen_loader.get_area('代理人-信息', '代理人-名称')
        self.switch_next_agent_area = self.ctx.screen_loader.get_area('代理人-信息', '按钮-下一位代理人')
        self.agent_skill_area = self.ctx.screen_loader.get_area('代理人-信息', '按钮-代理人技能')
        self.agent_core_skill_area = self.ctx.screen_loader.get_area('代理人-技能', '按钮-核心技')
        self.agent_drive_1_area = self.ctx.screen_loader.get_area('代理人-装备详细', '分区1')
        self.agent_drive_2_area = self.ctx.screen_loader.get_area('代理人-装备详细', '分区2')
        self.agent_drive_3_area = self.ctx.screen_loader.get_area('代理人-装备详细', '分区3')
        self.agent_drive_4_area = self.ctx.screen_loader.get_area('代理人-装备详细', '分区4')
        self.agent_drive_5_area = self.ctx.screen_loader.get_area('代理人-装备详细', '分区5')
        self.agent_drive_6_area = self.ctx.screen_loader.get_area('代理人-装备详细', '分区6')
        self.drive_disk_detail_area = self.ctx.screen_loader.get_area('代理人-装备详细', '驱动盘详细信息')
        self.equipment_area = self.ctx.screen_loader.get_area('代理人-装备详细', '替换')
        self.wengine_area = self.ctx.screen_loader.get_area('代理人-装备详细', '音擎')
        self.wengine_detail_area = self.ctx.screen_loader.get_area('代理人-装备详细', '音擎详细信息')
        # 前端值获取
        self.scan_agent_option = getattr(self.ctx, '_inventory_scan_agent_option', None)
    
    @operation_node(name='导航到代理人信息界面',is_start_node=True)
    def navigate_to_agent_info(self) -> OperationRoundResult:
        """导航到代理人信息界面"""
        return self.round_by_goto_screen(screen_name='代理人-信息')

    @node_from('导航到代理人信息界面')
    @operation_node(name='扫描特定代理人')
    def scan_specific_agent(self) -> OperationRoundResult:
        """扫描特定代理人"""
        iteration = 0
        max_iterations = 100
        while True:
            iteration += 1
            if iteration > max_iterations:
                return self.round_fail(f'特定扫描超过最大循环次数{max_iterations}强制结束')
            screen = self.screenshot()
            if screen is None:
                log.error("截图失败，无法获取屏幕画面")
                return self.round_fail('截图失败')
            crop_screen = cv2_utils.crop_image_only(screen, self.agent_name_area.rect)
            self.ocr_worker.submit('agent',crop_screen,self.agent_name_parser)
            self.ocr_worker.wait_complete()
            if self.ocr_worker.scanned_agents:
                agent_name = self.ocr_worker.scanned_agents[0]['key']
                self.ocr_worker.reset()
                if agent_name == self.scan_agent_option:
                    break
                else:
                    # 点击下一位代理人按钮
                    self.ctx.controller.click(self.switch_next_agent_area.rect.center)
                    time.sleep(0.3)# 等待下一位代理人加载完成
            else:
                return self.round_fail('特定扫描未检测到代理人姓名')
        return self.round_success('已扫描到特定代理人')
    
    @node_from('扫描特定代理人')
    @operation_node(name='获取特定代理人的基础信息')
    def get_agent_info(self) -> OperationRoundResult:
        """获取特定代理人的基础信息"""
        screen = self.screenshot()
        if screen is None:
            log.error("截图失败，无法获取屏幕画面")
            return self.round_fail('截图失败')
        #基础信息截图
        area_portrait = self.ctx.screen_loader.get_area('代理人-信息', '代理人-影画')
        area_name = self.ctx.screen_loader.get_area('代理人-信息', '代理人-名称')
        area_level = self.ctx.screen_loader.get_area('代理人-信息', '代理人-等级')
        self._img_portrait = cv2_utils.crop_image_only(screen, area_portrait.rect)
        self._img_name = cv2_utils.crop_image_only(screen, area_name.rect)
        self._img_level = cv2_utils.crop_image_only(screen, area_level.rect)

        self.round_by_goto_screen(screen_name='代理人-技能')# 导航到技能界面
        time.sleep(0.3)# 等待技能界面加载完成
        #return self.round_fail('已导航到特定代理人的技能界面')
        
        #技能信息截图
        screen = self.screenshot()
        if screen is None:
            log.error("截图失败，无法获取屏幕画面")
            return self.round_fail('截图失败')
        area_skill = self.ctx.screen_loader.get_area('代理人-技能', '代理人-技能等级')
        self._img_skill = cv2_utils.crop_image_only(screen, area_skill.rect)



        self.ctx.controller.click(self.agent_core_skill_area.rect.center)# 点击按钮到技能详细界面
        time.sleep(0.3)# 等待核心技等级界面加载完成

        #核心技等级信息截图
        screen = self.screenshot()
        if screen is None:
            log.error("截图失败，无法获取屏幕画面")
            return self.round_fail('截图失败')
        
        # 判断当前画面是否为'代理人-技能详细'
        from one_dragon.base.screen.screen_utils import is_target_screen
        if not is_target_screen(self.ctx, screen, screen_name='代理人-技能详细'):
            log.error("当前画面不是代理人-技能详细界面")
            return self.round_fail('导航到代理人-技能详细界面失败')
        
        area_core_skill = self.ctx.screen_loader.get_area('代理人-技能详细', '核心技等级')
        self._img_core_skill = cv2_utils.crop_image_only(screen, area_core_skill.rect)

        #拼接
        images = [
        self._img_portrait,  # 影画
        self._img_name,      # 名称
        self._img_level,     # 等级
        self._img_skill,     # 技能
        self._img_core_skill     # 核心技等级
        ]

        # 使用黑边padding统一宽度
        max_width = max(img.shape[1] for img in images)
        padded_images = []
        for img in images:
            if img.shape[1] < max_width:
                pad_left = (max_width - img.shape[1]) // 2
                pad_right = max_width - img.shape[1] - pad_left
                padded = cv2.copyMakeBorder(
                    img, 0, 0, pad_left, pad_right,
                    cv2.BORDER_CONSTANT, value=0
                )
                padded_images.append(padded)
            else:
                padded_images.append(img)
        # 上下拼接
        combined = np.vstack(padded_images)

        if combined is not None and combined.size > 0:
            self.ocr_worker.submit('agent',combined,self.agent_parser)
            # 等待ocr任务完成
            self.ocr_worker.wait_complete()
            #print('ocr任务完成')
            # 获取最新扫描的代理人数据（从列表末尾获取）
            if self.ocr_worker.scanned_agents:
                agent_info = self.ocr_worker.scanned_agents[-1].copy()
                self.agent_info = agent_info
                #print(f'当前扫描到的代理人数据为：{agent_info}')
                self.ocr_worker.reset()
                return self.round_success('获取特定代理人的基础信息完成')
            else:
                self.ocr_worker.reset()
                return self.round_fail('获取特定代理人的基础信息失败：未扫描到代理人数据')

        return self.round_fail('获取特定代理人的基础信息失败：截图拼接失败')
    
    # @node_from('获取特定代理人的基础信息')
    # @operation_node(name='回到代理人-信息界面')
    # def navigate_back_to_agent_info(self) -> OperationRoundResult:
    #     """回到代理人-信息界面"""
    #     return self.round_by_goto_screen(screen_name='代理人-信息')
    
    @node_from('获取特定代理人的基础信息')
    @operation_node(name='前往代理人装备详细页面')
    def navigate_to_agent_equipment(self) -> OperationRoundResult:
        """前往代理人装备详细页面"""
        return self.round_by_goto_screen(screen_name='代理人-装备详细')

    
    @node_from('前往代理人装备详细页面')
    @operation_node(name='获取代理人驱动盘')
    def get_agent_drive(self) -> OperationRoundResult:
        """获取代理人驱动盘"""
        for i in range(1, 7):
            area = getattr(self, f'agent_drive_{i}_area')
            self.ctx.controller.click(area.rect.center)#点击所有驱动盘
            time.sleep(0.3)# 等待驱动盘加载完成
            screen = self.screenshot()
            if screen is None:
                log.error("截图失败，无法获取屏幕画面")
                return self.round_fail('截图失败')
            ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
                    image=screen,
                    rect=self.equipment_area.rect,
                    color_range=self.equipment_area.color_range,
                    crop_first=True
            )
            #提交ocr任务
            if ocr_result_list:
                text = ocr_result_list[0].data
                #print(f'当前驱动盘状态为：{text}')
                if text =='卸下':
                    #print('当前驱动盘状态为卸下，提交ocr任务')
                    cropped_screen = cv2_utils.crop_image_only(screen, self.drive_disk_detail_area.rect)
                    self.ocr_worker.submit('disc',cropped_screen,self.drive_disk_parser)
        #print('等待ocr任务完成...')
        self.ocr_worker.wait_complete()
        #print('ocr任务完成')
        discs = self.ocr_worker.scanned_discs.copy()
        self.discs_data = discs
        #print(f'当前扫描到的驱动盘数据为：{discs}')
        self.ocr_worker.reset()    
        # for disc in discs:
        #         print(f"驱动盘套装: {disc.get('setKey')}, 等级: {disc.get('level')}\n")
        #         print(f"驱动盘品阶: {disc.get('rarity')}\n")
        #         print(f"驱动盘分区: {disc.get('slot_key')}\n")
        #         print(f"主属性: {disc.get('mainStatKey')}\n")
        #         print(f"副属性: {disc.get('substats')}\n")
        #         print(f'是否锁定: {disc.get("lock")}\n')
        #         print(f'是否被弃置: {disc.get("trash")}\n')
        #         print(f'驱动盘ID: {disc.get("id")}\n')
        return self.round_success('获取代理人驱动盘成功')        

    @node_from('获取代理人驱动盘')
    @operation_node(name='获取代理人武器')
    def get_agent_weapon(self) -> OperationRoundResult:
        """获取代理人武器"""
        self.ctx.controller.click(self.wengine_area.rect.center)#点击音擎
        time.sleep(0.3)# 等待音擎加载完成
        screen = self.screenshot()
        if screen is None:
            log.error("截图失败，无法获取屏幕画面")
            return self.round_fail('截图失败')
        ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
                    image=screen,
                    rect=self.equipment_area.rect,
                    color_range=self.equipment_area.color_range,
                    crop_first=True
            )
        if ocr_result_list:
            text = ocr_result_list[0].data
            #print(f'当前音擎状态为：{text}')
            if text =='卸下':
                #print('当前音擎状态为卸下，提交ocr任务')
                cropped_screen = cv2_utils.crop_image_only(screen, self.wengine_detail_area.rect)
                self.ocr_worker.submit('wengine',cropped_screen,self.wengine_parser)
        #print('等待ocr任务完成...')
        self.ocr_worker.wait_complete()
        #print('ocr任务完成')
        wengine = self.ocr_worker.scanned_wengines.copy()
        self.wengine_data = wengine
        #print(f'当前扫描到的音擎数据为：{wengine}')
        self.ocr_worker.reset()    
        return self.round_success('获取代理人武器成功')
    
    @node_from('获取代理人武器')
    @operation_node(name='生成json文件')
    def generate_json(self) -> OperationRoundResult:
        """生成json文件"""
        agent=self.agent_info
        discs = self.discs_data
        weapon=self.wengine_data
        
        # import time
        # now_time = time.strftime("%Y%m%d%H%M%S", time.localtime())
        
        # 填充 equippedDiscs 字段（包含完整驱动盘信息）
        equipped_discs = {}
        if discs:
            for disc in discs:
                slot_key = disc.get('slotKey', '')
                if slot_key:
                    equipped_discs[slot_key] = disc  # 存储完整的驱动盘数据
        agent['equippedDiscs'] = equipped_discs
        
        # 填充 equippedWengine 字段（包含完整音擎信息）
        wengine_data = {}
        if weapon:
            wengine_data = weapon[0]  # 存储完整的音擎数据
        agent['equippedWengine'] = wengine_data

        try:
                # 确保目录存在
                os.makedirs(self.data_file_path, exist_ok=True)
                # 使用 os.path.join 拼接路径
                json_file_path = os.path.join(self.data_file_path, f'{self.scan_agent_option}_data.json')
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(agent, f, ensure_ascii=False, indent=4)
                    #print(f'已将数据写入文件: {json_file_path}')
        except Exception as e:
                return self.round_fail(f'写数据到JSON文件失败: {e}')  
        return self.round_success('代理人扫描完成并生成json文件成功')  
    
           
