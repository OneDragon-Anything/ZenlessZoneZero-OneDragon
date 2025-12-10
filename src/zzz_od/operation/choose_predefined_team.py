import time

import difflib
from typing import List

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum


class ChoosePredefinedTeam(ZOperation):

    def __init__(self, ctx: ZContext, target_team_idx_list: List[int]):
        """
        在出战画面使用
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name='%s %s' % (gt('选择预备编队'), target_team_idx_list))

        self.target_team_idx_list: List[int] = target_team_idx_list
        self.choose_fail_times: int = 0  # 选择失败的次数
        self.selected_times: int = 0  # 选择成功的次数

    @operation_node(name='画面识别', node_max_retry_times=10, is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        result = self.round_by_find_area(self.last_screenshot, '实战模拟室', '预备编队')
        if result.is_success:
            return self.round_success(result.status)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='画面识别', status='预备编队')
    @operation_node(name='点击预备编队')
    def click_team(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(self.last_screenshot, '实战模拟室', '预备编队',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击预备编队')
    @node_from(from_name='选择编队失败')
    @operation_node(name='选择编队')
    def choose_team(self) -> OperationRoundResult:
        # 有时候灰色的'预备出战'也能被ocr到导致死循环, 改为识别成功次数
        if self.selected_times == len(self.target_team_idx_list):
            return self.round_success()

        team_list = self.ctx.team_config.team_list

        for target_team_idx in self.target_team_idx_list:
            if team_list is None or target_team_idx >= len(team_list):
                return self.round_fail('选择的预备编队下标错误 %s' % target_team_idx)

            target_team_name = team_list[target_team_idx].name

            ocr_map = self.ctx.ocr.run_ocr(self.last_screenshot)
            target_list = list(ocr_map.keys())
            best_match = difflib.get_close_matches(target_team_name, target_list, n=1)

            if best_match is None or len(best_match) == 0:
                return self.round_retry(wait=0.5)

            ocr_result: MatchResultList = ocr_map.get(best_match[0], None)
            if ocr_result is None or ocr_result.max is None:
                return self.round_retry(wait=0.5)

            to_click = ocr_result.max.center + Point(200, 0)

            # 点击之前的队伍选择个数
            selected_count_before_click = self.find_selected_num(self.last_screenshot)
            self.ctx.controller.click(to_click)

            time.sleep(1)

            # 点击之后的队伍选择个数
            selected_count_after_click = self.find_selected_num(self.screenshot())
            if 1 + selected_count_before_click == selected_count_after_click:
                # 选择成功
                self.selected_times += 1
                continue
            elif selected_count_before_click == selected_count_after_click:
                # 点了没反应
                return self.round_wait()
            else:
                # ocr出问题了, 再点一遍并认为已选择成功
                self.ctx.controller.click(to_click)
                self.selected_times += 1
                log.error('无法识别队伍选择结果, 认为已选择成功')
                continue

        return self.round_wait()

    @node_from(from_name='选择编队', success=False)
    @operation_node(name='选择编队失败')
    def choose_team_fail(self) -> OperationRoundResult:
        self.choose_fail_times += 1
        if self.choose_fail_times >= 2:
            return self.round_fail('选择配队失败')

        drag_start = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
        drag_end = drag_start + Point(0, -500)
        self.ctx.controller.drag_to(start=drag_start, end=drag_end)
        return self.round_success(wait=1)

    @node_from(from_name='选择编队')
    @operation_node(name='选择编队确认')
    def click_confirm(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(self.last_screenshot, '实战模拟室', '预备出战')
        if result.is_success:
            time.sleep(0.5)
            self.ctx.controller.mouse_move(ScreenNormalWorldEnum.UID.value.center)  # 点击后 移开鼠标 防止识别不到出战
            return self.round_success(result.status, wait=0.5)
        else:
            return self.round_retry(result.status, wait=1)

    # 在特定区域中查找 'SELECTED' 的个数, 用于判断是否成功选择了队伍
    def find_selected_num(self, screen):
        selected_area_list = [
            '预备编队选择成功1',
            '预备编队选择成功2'
        ]

        count = 0
        for area_name in selected_area_list:
            area = self.ctx.screen_loader.get_area('实战模拟室', area_name)
            if area is None:
                return 0
            to_ocr_part = cv2_utils.crop_image_only(screen, area.rect)
            ocr_map = self.ctx.ocr.run_ocr(to_ocr_part)
            target_list = list(ocr_map.keys())

            count += sum(1 for target in target_list if 'SELECTED' == target)
        return count


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()

    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('img')
    print(ctx.ocr.run_ocr(screen))


if __name__ == '__main__':
    __debug()
