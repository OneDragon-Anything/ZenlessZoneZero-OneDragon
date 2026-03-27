import time
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.application.inventory_scan.special_scan import special_scan_const
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from one_dragon.base.screen.screen_utils import FindAreaResultEnum, find_area_in_screen

class SpecialScanApp(ZApplication):
    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=special_scan_const.APP_ID,
            op_name=special_scan_const.APP_NAME,
        )
        # 区域配置
        self.agent_name_area = self.ctx.screen_loader.get_area('代理人-信息', '代理人-名称')
        self.switch_next_agent_area = self.ctx.screen_loader.get_area('代理人-信息', '按钮-下一位代理人')
        self.agent_drive_1_area = self.ctx.screen_loader.get_area('代理人-装备', '分区1')
        self.agent_drive_2_area = self.ctx.screen_loader.get_area('代理人-装备', '分区2')
        self.agent_drive_3_area = self.ctx.screen_loader.get_area('代理人-装备', '分区3')
        self.agent_drive_4_area = self.ctx.screen_loader.get_area('代理人-装备', '分区4')
        self.agent_drive_5_area = self.ctx.screen_loader.get_area('代理人-装备', '分区5')
        self.agent_drive_6_area = self.ctx.screen_loader.get_area('代理人-装备', '分区6')
        # 前端值获取
        self.scan_agent_option = getattr(self.ctx, '_inventory_scan_agent_option', None)
        # 最大迭代次数
        self.max_iterations = 100

    @operation_node(name='返回大世界-普通',is_start_node=True)
    def back_at_first(self) -> OperationRoundResult:
        """返回大世界"""
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())
    
    @node_from('返回大世界-普通')
    @operation_node(name='导航到代理人信息界面')
    def navigate_to_agent_info(self) -> OperationRoundResult:
        """导航到代理人信息界面"""
        return self.round_by_goto_screen(screen_name='代理人-信息')

    @node_from('导航到代理人信息界面')
    @operation_node(name='扫描特定代理人')
    def scan_specific_agent(self) -> OperationRoundResult:
        """扫描特定代理人"""
        iteration = 0
        while True:
            iteration += 1
            if iteration > self.max_iterations:
                return self.round_fail(f'特定扫描超过最大循环次数{self.max_iterations}强制结束')
            screen=self.ctx.controller.get_screenshot()
            ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
                    image=screen,
                    rect=self.agent_name_area.rect,
                    color_range=self.agent_name_area.color_range,
                    crop_first=True
            )
            if ocr_result_list:
                agent_name = ocr_result_list[0].data
                #print(f'当前扫描到的代理人姓名为：{agent_name}')
                if agent_name == self.scan_agent_option:
                    break
                else:
                    # 点击下一位代理人按钮
                    self.ctx.controller.click(self.switch_next_agent_area.rect.center)
                    time.sleep(0.3)# 等待下一位代理人加载完成
            else:
                return self.round_fail('特定扫描未检测到代理人姓名')
        return self.round_success('特定扫描完成')
    
    @node_from('扫描特定代理人')
    @operation_node(name='前往代理人装备页面')
    def navigate_to_agent_equipment(self) -> OperationRoundResult:
        """前往代理人装备页面"""
        return self.round_by_goto_screen(screen_name='代理人-装备')
    
    @node_from('前往代理人装备页面')
    @operation_node(name='获取代理人驱动盘')
    def get_agent_drive(self) -> OperationRoundResult:
        """获取代理人驱动盘"""
        self.ctx.controller.click(self.agent_drive_1_area.rect.center)#示例点击第一个驱动盘
        return self.round_success('获取代理人驱动盘成功')
           
