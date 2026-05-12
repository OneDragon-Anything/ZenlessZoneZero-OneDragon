from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from one_dragon.utils import cv2_utils
from zzz_od.application.back_to_world import back_to_world_const
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.application.inventory_scan.parser.agent_name_parser import AgentNameParser
import time


class BackToWorldApp(ZApplication):

    def __init__(self, ctx: ZContext):
        """
        返回大世界应用
        将游戏从任何状态智能返回到大世界（普通世界）
        """
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=back_to_world_const.APP_ID,
            op_name=back_to_world_const.APP_NAME,
        )
        # 获取选择的代理人代码（从 context 中获取）
        self.selected_agent_code = getattr(self.ctx, '_back_to_world_agent_code', None)
        # 初始化代理人名称解析器
        self.agent_name_parser = AgentNameParser()

    def handle_init(self) -> None:
        """
        执行前的初始化 由子类实现
        注意初始化要全面 方便一个指令重复使用
        """
        pass

    @operation_node(name='返回大世界', is_start_node=True)
    def back_to_world(self) -> OperationRoundResult:
        """
        返回大世界
        :return:
        """
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())
    
    @node_from(from_name='返回大世界')
    @operation_node(name='导航到特定代理人')
    def navigate_to_agent_info(self) -> OperationRoundResult:
        """
        导航到代理人-信息画面
        :return:
        """
        result = self.round_by_goto_screen(screen_name='代理人-信息')
        if not result.is_success:
            return result
        
        # 如果没有选择代理人，直接返回成功
        if not self.selected_agent_code:
            log.info("未选择代理人，停留在代理人-信息界面")
            return self.round_success('已导航到代理人-信息界面')
        
        # 如果有选择代理人，则导航到该代理人
        return self._navigate_to_specific_agent()
    
    def _navigate_to_specific_agent(self) -> OperationRoundResult:
        """
        导航到指定的代理人
        参考 special_scan_app.py 的实现方式
        :return:
        """
        log.info(f"开始导航到代理人: {self.selected_agent_code}")
        
        # 获取代理人名称区域和切换按钮区域
        agent_name_area = self.ctx.screen_loader.get_area('代理人-信息', '代理人-名称')
        switch_next_agent_area = self.ctx.screen_loader.get_area('代理人-信息', '按钮-下一位代理人')
        
        # 最大循环次数，避免无限循环
        max_iterations = 100
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # 截图
            screen = self.screenshot()
            if screen is None:
                log.error("截图失败，无法获取屏幕画面")
                return self.round_fail('截图失败')
            
            # 裁剪代理人名称区域
            cropped_screen = cv2_utils.crop_image_only(screen, agent_name_area.rect)
            
            # 使用 OCR 服务识别代理人名称
            ocr_result_list = self.ctx.ocr_service.get_ocr_result_list(
                image=cropped_screen,
                rect=None,
                crop_first=False
            )
            
            if not ocr_result_list or len(ocr_result_list) == 0:
                log.warning("OCR 未识别到任何文本")
                # 点击下一位代理人按钮
                self.ctx.controller.click(switch_next_agent_area.rect.center)
                time.sleep(0.3)
                continue
            
            # 将 OcrMatchResult 转换为字典格式（参考 agent_parser 的期望格式）
            ocr_items = [
                {
                    "text": item.data,
                    "confidence": item.confidence
                }
                for item in ocr_result_list
            ]
            
            # 使用 AgentNameParser 解析 OCR 结果
            parsed_result = self.agent_name_parser.parse_ocr_result(
                ocr_items,
                cropped_screen
            )
            
            if not parsed_result:
                log.warning("未能解析到代理人名称")
                # 点击下一位代理人按钮
                self.ctx.controller.click(switch_next_agent_area.rect.center)
                time.sleep(0.3)
                continue
            
            # 获取解析后的代理人代码（英文）
            current_agent_code = parsed_result.get('key', '')
            log.info(f"当前代理人代码: {current_agent_code}, 目标代理人代码: {self.selected_agent_code}")
            
            # 检查是否匹配
            if current_agent_code == self.selected_agent_code:
                log.info(f"已找到目标代理人: {self.selected_agent_code}")
                return self.round_success(f'已导航到代理人: {self.selected_agent_code}')
            
            # 不匹配，点击下一位代理人按钮
            self.ctx.controller.click(switch_next_agent_area.rect.center)
            time.sleep(0.3)  # 等待下一位代理人加载完成
        
        return self.round_fail(f'未找到目标代理人: {self.selected_agent_code}，已超过最大循环次数')


def __debug():
    """
    调试函数
    用于测试返回大世界应用
    """
    ctx = ZContext()
    ctx.init_by_config()
    app = BackToWorldApp(ctx)
    app.execute()


if __name__ == '__main__':
    __debug()
