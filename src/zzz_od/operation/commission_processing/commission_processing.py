from typing import ClassVar, Optional

import time
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.controller.pc_controller_base import PcControllerBase
from one_dragon.utils import str_utils, cv2_utils
from one_dragon.utils.i18_utils import gt
from zzz_od.application.commission_processing.commission_processing_run_record import CommissionProcessingRunRecord
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.operation.back_to_normal_world import BackToNormalWorld


class CommissionProcessing(ZOperation):

    def __init__(self, ctx: ZContext, run_record: Optional[CommissionProcessingRunRecord] = None):
        ZOperation.__init__(self, ctx, op_name=gt('委托处理', 'ui'))
        self.run_record: Optional[CommissionProcessingRunRecord] = run_record
        self.scroll_times: int = 0
        self.current_commission_type: Optional[str] = None
        self.battle_result_retry_times: int = 0
        self.has_filtered: bool = False



    @operation_node(name='返回大世界', is_start_node=True)
    def back_to_world(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='返回大世界')
    @operation_node(name='打开情报板')
    def open_board(self) -> OperationRoundResult:
        # 1. 在大世界按 ~
        if isinstance(self.ctx.controller, PcControllerBase):
            self.ctx.controller.keyboard_controller.press('`', press_time=0.2)
        return self.round_success(wait=1)

    @node_from(from_name='打开情报板')
    @operation_node(name='点击情报板')
    def click_board(self) -> OperationRoundResult:
        # 2. OCR 点击情报板
        screen = self.last_screenshot
        ocr_results = self.ctx.ocr_service.get_ocr_result_list(screen)
        idx = str_utils.find_best_match_by_difflib(gt('情报板', 'game'), [i.data for i in ocr_results])
        
        if idx is not None:
            self.ctx.controller.click(ocr_results[idx].center)
            return self.round_success(wait=1)
        
        return self.round_retry('未找到情报板')

    @node_from(from_name='检查进度', success=False)
    @node_from(from_name='检查接取结果', status='接取失败')
    @operation_node(name='刷新委托')
    def refresh_commission(self) -> OperationRoundResult:
        # 3. 点击下面的刷新
        self.ctx.controller.click(self.ctx.screen_loader.get_area('委托情报板', '刷新按钮').rect.center)

        if self.has_filtered:
            self.scroll_times = 0
            return self.round_success(wait=1)

        time.sleep(1)
        self.ctx.controller.click(self.ctx.screen_loader.get_area('委托情报板', '筛选按钮').center)

        time.sleep(0.5)

        # OCR 找 重置
        screen = self.screenshot()
        ocr_results = self.ctx.ocr_service.get_ocr_result_list(screen)
        idx = str_utils.find_best_match_by_difflib(gt('重置', 'game'), [i.data for i in ocr_results])
        if idx is not None:
            self.ctx.controller.click(ocr_results[idx].center)
        else:
            self.ctx.controller.click(self.ctx.screen_loader.get_area('委托情报板', '重置按钮').center)
        time.sleep(0.5)

        # OCR 找 恶名狩猎 和 专业挑战室
        search_rect = self.ctx.screen_loader.get_area('委托情报板', '搜索区域').rect
        screen = self.screenshot()
        part = cv2_utils.crop_image_only(screen, search_rect)
        ocr_results = self.ctx.ocr_service.get_ocr_result_list(part)
        ocr_texts = [i.data for i in ocr_results]

        # 恶名狩猎
        idx = str_utils.find_best_match_by_difflib(gt('恶名狩猎', 'game'), ocr_texts)
        if idx is not None:
            center = ocr_results[idx].center + search_rect.left_top
            self.ctx.controller.click(center)
        else:
            self.ctx.controller.click(self.ctx.screen_loader.get_area('委托情报板', '恶名狩猎兜底').center)
        time.sleep(0.5)

        # 专业挑战室
        idx = str_utils.find_best_match_by_difflib(gt('专业挑战室', 'game'), ocr_texts)
        if idx is not None:
            center = ocr_results[idx].center + search_rect.left_top
            self.ctx.controller.click(center)
        else:
            self.ctx.controller.click(self.ctx.screen_loader.get_area('委托情报板', '专业挑战室兜底').center)
        time.sleep(0.5)

        self.ctx.controller.click(self.ctx.screen_loader.get_area('委托情报板', '关闭筛选').center)
        time.sleep(0.5)

        self.has_filtered = True
        self.scroll_times = 0  # 重置翻页次数
        return self.round_success(wait=1)

    @node_from(from_name='刷新委托')
    @node_from(from_name='寻找委托', status='翻页')
    @operation_node(name='寻找委托')
    def find_commission(self) -> OperationRoundResult:
        # 4. Ocr 专业挑战室/恶名狩猎，找不到就往下翻到找到为止
        screen = self.screenshot()
        ocr_results = self.ctx.ocr_service.get_ocr_result_list(screen)
        
        # 使用字典映射委托名称到类型，方便扩展
        commission_map = {
            gt('专业挑战室', 'game'): 'expert_challenge',
            gt('恶名狩猎', 'game'): 'notorious_hunt',
        }

        for res in ocr_results:
            for target_text, commission_type in commission_map.items():
                if target_text in res.data:
                    self.ctx.controller.click(res.center)
                    self.current_commission_type = commission_type
                    return self.round_success(res.data)
        
        # 翻页
        if self.scroll_times >= 5:
            return self.round_success(status='无委托')

        self.scroll_times += 1
        self.ctx.controller.scroll(200, Point(960, 540)) # 简单的滚动尝试
        return self.round_wait(status='翻页', wait=1)

    @node_from(from_name='寻找委托')
    @operation_node(name='接取委托')
    def accept_commission(self) -> OperationRoundResult:
        # 5. 点击（ocr）接取委托
        screen = self.screenshot()
        ocr_results = self.ctx.ocr_service.get_ocr_result_list(screen)
        ocr_texts = [i.data for i in ocr_results]
        
        idx = str_utils.find_best_match_by_difflib(gt('接取委托', 'game'), ocr_texts)
        
        if idx is not None:
            self.ctx.controller.click(ocr_results[idx].center)
            return self.round_success(wait=1)
        
        # 兜底：如果已经是进行中，或者有前往按钮
        if str_utils.find_best_match_by_difflib(gt('前往', 'game'), ocr_texts) is not None:
             return self.round_success(wait=1)
        
        # 模糊匹配 委托进行中
        for text in ocr_texts:
            if gt('委托进行中', 'game') in text:
                return self.round_success(wait=1)
        
        return self.round_retry('未找到接取委托')

    @node_from(from_name='接取委托')
    @operation_node(name='检查接取结果')
    def check_accept_result(self) -> OperationRoundResult:
        screen = self.screenshot()
        ocr_results = self.ctx.ocr_service.get_ocr_result_list(screen)
        ocr_texts = [i.data for i in ocr_results]

        if str_utils.find_best_match_by_difflib(gt('接取失败', 'game'), ocr_texts) is not None:
            return self.round_success(status='接取失败')

        return self.round_success(status='接取成功')

    @node_from(from_name='检查接取结果', status='接取成功')
    @operation_node(name='前往')
    def go_to_commission(self) -> OperationRoundResult:
        # 6. ocr 前往并点击
        screen = self.screenshot()
        ocr_results = self.ctx.ocr_service.get_ocr_result_list(screen)
        idx = str_utils.find_best_match_by_difflib(gt('前往', 'game'), [i.data for i in ocr_results])
        
        if idx is not None:
            self.ctx.controller.click(ocr_results[idx].center)
            return self.round_success(wait=2) # 等待加载
        
        return self.round_retry('未找到前往')

    @node_from(from_name='前往')
    @operation_node(name='下一步')
    def next_step(self) -> OperationRoundResult:
        # 7. 点击下一步然后进入战斗
        screen = self.screenshot()
        ocr_results = self.ctx.ocr_service.get_ocr_result_list(screen)
        ocr_texts = [i.data for i in ocr_results]
        
        idx = str_utils.find_best_match_by_difflib(gt('下一步', 'game'), ocr_texts)
        
        if idx is not None:
            self.ctx.controller.click(ocr_results[idx].center)
            return self.round_wait(wait=1)
        
        # 检查是否已经进入战斗准备（出战）
        idx_battle = str_utils.find_best_match_by_difflib(gt('出战', 'game'), ocr_texts)
        if idx_battle is not None:
            self.ctx.controller.click(ocr_results[idx_battle].center)
            return self.round_success('进入战斗')

        # 检查无报酬模式 (恶名狩猎)
        idx_no_reward = str_utils.find_best_match_by_difflib(gt('无报酬模式', 'game'), ocr_texts)
        if idx_no_reward is not None:
            self.ctx.controller.click(ocr_results[idx_no_reward].center)
            return self.round_wait(wait=1)

        return self.round_retry('未找到下一步或出战')

    @node_from(from_name='下一步')
    @operation_node(name='开始自动战斗')
    def start_auto_battle(self) -> OperationRoundResult:
        self.ctx.auto_battle_context.init_auto_op(op_name='全配队通用')
        self.ctx.auto_battle_context.start_auto_battle()
        return self.round_success()

    @node_from(from_name='开始自动战斗')
    @operation_node(name='战斗中')
    def in_battle(self) -> OperationRoundResult:
        
        screen = self.screenshot()

        # 1. 先同步检查战斗状态，避免 OCR 竞态
        self.ctx.auto_battle_context.check_battle_state(
            screen, self.last_screenshot_time,
            check_battle_end_normal_result=True,
            sync=True
        )

        # 2. 检查是否结束
        if self.ctx.auto_battle_context.last_check_end_result is not None:
            self.ctx.auto_battle_context.stop_auto_battle()
            self.battle_result_retry_times = 0
            return self.round_success('战斗结束')

        # 3. 额外的 OCR 检查 (委托代行中)
        # 此时 check_battle_state 已完成，可以安全调用 OCR
        ocr_results = self.ctx.ocr_service.get_ocr_result_list(screen)
        ocr_texts = [i.data for i in ocr_results]

        # 特殊处理：委托代行中 提示
        if str_utils.find_best_match_by_difflib(gt('委托代行中', 'game'), ocr_texts) is not None:
            idx_confirm = str_utils.find_best_match_by_difflib(gt('确认', 'game'), ocr_texts)
            if idx_confirm is not None:
                self.ctx.controller.click(ocr_results[idx_confirm].center)
                return self.round_wait(wait=1)
        
        return self.round_wait(status='自动战斗中', wait=self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='战斗中')
    @operation_node(name='战斗结算')
    def battle_result(self) -> OperationRoundResult:
        screen = self.screenshot()
        ocr_results = self.ctx.ocr_service.get_ocr_result_list(screen)
        ocr_texts = [i.data for i in ocr_results]
        
        # 1. 检查是否回到委托列表界面 (通过关键词 周期内可获取)
        if str_utils.find_best_match_by_difflib(gt('周期内可获取', 'game'), ocr_texts) is not None:
            if self.run_record is not None and self.current_commission_type is not None:
                if self.current_commission_type == 'expert_challenge':
                    self.run_record.expert_challenge_count += 1
                elif self.current_commission_type == 'notorious_hunt':
                    self.run_record.notorious_hunt_count += 1
                self.current_commission_type = None  # 重置

            return self.round_success('结算完成')

        # 2. 检查 "代行委托完成"
        if str_utils.find_best_match_by_difflib(gt('代行委托完成', 'game'), ocr_texts) is not None:
            # 点击确认 (中间右边)
            idx = str_utils.find_best_match_by_difflib(gt('确认', 'game'), ocr_texts)
            if idx is not None:
                self.ctx.controller.click(ocr_results[idx].center)
            self.battle_result_retry_times = 0
            return self.round_wait(wait=1)

        # 3. 点击结算按钮 (完成/下一步)
        targets = [gt('完成', 'game'), gt('下一步', 'game'), gt('确认', 'game')]
        for target in targets:
            idx = str_utils.find_best_match_by_difflib(target, ocr_texts)
            if idx is not None:
                self.ctx.controller.click(ocr_results[idx].center)
                self.battle_result_retry_times = 0
                return self.round_wait(wait=1)
        
        self.battle_result_retry_times += 1
        if self.battle_result_retry_times > 60:
            return self.round_fail('战斗结算卡死')

        return self.round_wait(wait=1)

    @node_from(from_name='战斗结算')
    @node_from(from_name='点击情报板')
    @operation_node(name='检查进度')
    def check_progress(self) -> OperationRoundResult:
        # 8. ocr 645, 2039和1026, 2123之间
        rect = self.ctx.screen_loader.get_area('委托情报板', '进度文本').rect
        screen = self.last_screenshot
        part = cv2_utils.crop_image_only(screen, rect)
        ocr_result = self.ctx.ocr.run_ocr_single_line(part)

        if '1000/1000' in ocr_result:
            return self.round_success('完成')

        # 解析数字 xx/1000
        try:
            # 移除可能的非数字字符（除了 /）
            clean_text = ''.join([c for c in ocr_result if c.isdigit() or c == '/'])
            if '/' in clean_text:
                parts = clean_text.split('/')
                if len(parts) >= 2:
                    current = int(parts[0])
                    total = int(parts[1])
                    if total > 0 and current >= total:
                        return self.round_success('完成')
                    # 只要第一个数字是1000也算完成
                    if current >= 1000:
                        return self.round_success('完成')
        except Exception as e:
            return self.round_fail(f'解析进度文本失败: {ocr_result}, 错误: {e}')
        
        return self.round_fail('继续')

    @node_from(from_name='检查进度')
    @node_from(from_name='寻找委托', status='无委托')
    @operation_node(name='结束处理')
    def finish_processing(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        result = op.execute()
        if not result.success:
            return self.round_by_op_result(result)

        # 打开暂停菜单
        if isinstance(self.ctx.controller, PcControllerBase):
            self.ctx.controller.keyboard_controller.press('esc', press_time=0.2)

        status = '完成'
        if self.run_record is not None:
            status = f'完成 恶名狩猎: {self.run_record.notorious_hunt_count}, 专业挑战室: {self.run_record.expert_challenge_count}'

        return self.round_success(status)
