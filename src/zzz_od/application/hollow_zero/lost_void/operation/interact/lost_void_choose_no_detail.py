import time

from cv2.typing import MatLike
from typing import List

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidChooseNoDetail(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        没有详情 但有显示选择数量的选择
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name='迷失之地-无详情选择')

        self.chosen_idx_list: list[int] = []  # 已经选择过的下标

    @operation_node(name='选择', is_start_node=True)
    def choose_artifact(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('迷失之地-通用选择', '文本-详情')
        self.ctx.controller.mouse_move(area.center + Point(0, 100))
        time.sleep(0.1)

        screen = self.screenshot()

        screen_name = self.check_and_update_current_screen()
        if screen_name != '迷失之地-无详情选择':
            # 进入本指令之前 有可能识别错画面
            return self.round_retry(status=f'当前画面 {screen_name}', wait=1)

        # 目前这两个画面的判断重叠 需要返回外层重新处理
        result = self.round_by_find_area(screen, '迷失之地-通用选择', '文本-详情')
        if result.is_success:
            self.ctx.screen_loader.update_current_screen_name('迷失之地-通用选择')
            return self.round_success('迷失之地-通用选择')

        art_list = self.get_artifact_pos(screen)
        if len(art_list) == 0:
            return self.round_retry(status='无法识别藏品', wait=1)

        # 可能出现无法选择的选项 需要将之前选择过的进行排除
        priority_list = self.ctx.lost_void.get_artifact_by_priority(art_list, 1,
                                                                    ignore_idx_list=self.chosen_idx_list)
        for art in priority_list:
            for idx, art_2 in enumerate(art_list):
                if art_2 == art:  # 需要保证 get_artifact_by_priority 返回的是原对象
                    self.chosen_idx_list.append(idx)
                    break
            self.ctx.controller.click(art.center)
            time.sleep(0.5)
            break

        return self.round_success()

    def get_artifact_pos(self, screen: MatLike) -> List[MatchResult]:
        """
        获取藏品的位置
        @param screen: 游戏画面
        @return: 识别到的武备的位置
        """
        area = self.ctx.screen_loader.get_area('迷失之地-无详情选择', '区域-藏品名称')
        part = cv2_utils.crop_image_only(screen, area.rect)

        result_list: List[MatchResult] = []

        ocr_result_map = self.ctx.ocr.run_ocr(part)
        for ocr_result, mrl in ocr_result_map.items():
            art = self.ctx.lost_void.match_artifact_by_ocr_full(ocr_result)
            if art is None:
                continue

            result = mrl.max
            result.add_offset(area.left_top)
            result.data = art
            result_list.append(result)

        display_text = ','.join([i.data.display_name for i in result_list]) if len(result_list) > 0 else '无'
        log.info(f'当前识别藏品 {display_text}')

        return result_list

    @node_from(from_name='选择')
    @operation_node(name='点击确定')
    def click_confirm(self) -> OperationRoundResult:
        screen = self.screenshot()

        # 可能会触发二次选择
        result = self.round_by_find_area(screen, '迷失之地-通用选择', '文本-详情')
        if result.is_success:
            self.ctx.screen_loader.update_current_screen_name('迷失之地-通用选择')
            return self.round_success('迷失之地-通用选择')

        return self.round_by_find_and_click_area(screen_name='迷失之地-无详情选择', area_name='按钮-确定',
                                                 success_wait=1, retry_wait=1,
                                                 until_not_find_all=[('迷失之地-无详情选择', '按钮-确定')])


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.ocr.init_model()
    ctx.lost_void.init_before_run()
    ctx.start_running()

    op = LostVoidChooseNoDetail(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()