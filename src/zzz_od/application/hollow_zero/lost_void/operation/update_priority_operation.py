import re
from typing import List

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class UpdatePriorityOperation(ZOperation):

    def __init__(self, ctx: ZContext):
        super().__init__(ctx, op_name='更新动态优先级')

    @operation_node(name='进入藏品页面')
    def enter_collections(self) -> OperationRoundResult:
        # 1: 打开菜单
        result = self.round_by_find_and_click_area(screen_name='迷失之地-大世界', area_name='迷失之地-TAB')
        if result.is_success:
            return self.round_wait(status=result.status, wait=1)

        # 2: 切换到藏品页
        result = self.round_by_find_and_click_area(screen_name='迷失之地-藏品面板', area_name='藏品')
        if result.is_success:
            return self.round_success(status=result.status, wait=1)

        # 失败了就让框架从打开菜单开始重试整个节点 因为有可能会出现菜单按钮点到了但实际没打开的情况
        return self.round_retry(status=result.status, wait=1)

    @node_from(from_name='进入藏品页面')
    @operation_node(name='识别并存储优先级')
    def recognize_and_store(self) -> OperationRoundResult:
        """
        使用CV流水线识别藏品，并通过空间关联，识别等级1或2的武备，并提取其分类作为优先级
        """
        # 1. 使用CV流水线识别藏品
        log.info("开始执行CV流水线 [迷失之地-藏品类型识别]...")
        pipeline_result = self.ctx.cv_service.run_pipeline('迷失之地-藏品类型识别', self.last_screenshot)

        if not pipeline_result.ocr_result:
            log.info("流水线未识别到任何藏品，动态优先级设置为空")
            self.ctx.lost_void.dynamic_priority_list = []
            return self.round_success("未发现需优先的藏品")

        all_match_results_with_text = []
        for text, mrl in pipeline_result.ocr_result.items():
            for mr in mrl:
                mr.text = text  # Manually attach text to each MatchResult
                all_match_results_with_text.append(mr)

        # 按Y坐标排序
        sorted_text_blocks = sorted(all_match_results_with_text, key=lambda mr: mr.rect.y1)

        # 2. 找到所有“等级X”的文本块
        level_blocks = []
        for block in sorted_text_blocks:
            if "等级1" in block.text or "等级2" in block.text:
                level_blocks.append(block)

        if not level_blocks:
            log.info("未识别到任何等级1或等级2的藏品")
            self.ctx.lost_void.dynamic_priority_list = []
            return self.round_success("未发现需优先的藏品")

        # 3. 为每个“等级X”找到其上方的藏品名称
        new_priorities = set()
        for level_block in level_blocks:
            best_candidate = None
            min_distance = float('inf')

            for potential_name_block in sorted_text_blocks:
                if potential_name_block is level_block:
                    continue
                # 必须在等级块的上方
                if potential_name_block.rect.y2 > level_block.rect.y1:
                    continue

                # X坐标必须有重叠，以确保是同一个藏品
                x_overlap = max(0, min(potential_name_block.rect.x2, level_block.rect.x2) - max(
                    potential_name_block.rect.x1, level_block.rect.x1))
                if x_overlap == 0:
                    continue

                distance = level_block.rect.y1 - potential_name_block.rect.y2
                if distance < min_distance:
                    min_distance = distance
                    best_candidate = potential_name_block

            if best_candidate:
                # 4. 匹配并提取category
                artifact = self.ctx.lost_void.match_artifact_by_ocr_full(best_candidate.text)
                # 5. 判断是否为“武备”
                if artifact and artifact.is_gear:
                    log.info(f"发现低等级【武备】: {artifact.display_name}，添加优先级: {artifact.category}")
                    new_priorities.add(artifact.category)
                elif artifact:
                    log.debug(f"发现低等级【非武备】藏品: {artifact.display_name}，已忽略")

        # 6. 存储最终结果
        self.ctx.lost_void.dynamic_priority_list = list(new_priorities)
        log.debug(f"动态优先级列表已更新: {self.ctx.lost_void.dynamic_priority_list}")
        return self.round_success("动态优先级存储成功")

    @node_from(from_name='识别并存储优先级')
    @operation_node(name='关闭菜单')
    def close_menu(self) -> OperationRoundResult:
        """
        点击返回按钮关闭菜单
        """
        return self.round_by_find_and_click_area(screen_name='迷失之地-藏品面板', area_name='返回按钮',
                                                 success_wait=1, retry_wait=1,
                                                 until_not_find_all=[('迷失之地-藏品面板', '返回按钮')])

def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.lost_void.init_before_run()
    ctx.run_context.start_running()
    op = UpdatePriorityOperation(ctx)
    op.execute()
    ctx.run_context.stop_running()


if __name__ == '__main__':
    __debug()
