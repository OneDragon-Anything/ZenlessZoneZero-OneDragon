import time

import difflib
from typing import List

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
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
        self.choose_fail_times: int = 0   # 选择失败的次数

    @operation_node(name='画面识别', node_max_retry_times=10, is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        screen = self.screenshot()

        result = self.round_by_find_area(screen, '实战模拟室', '预备编队')
        if result.is_success:
            return self.round_success(result.status)

        return self.round_retry(result.status, wait=1)

    @node_from(from_name='画面识别', status='预备编队')
    @operation_node(name='点击预备编队')
    def click_team(self) -> OperationRoundResult:
        screen = self.screenshot()
        return self.round_by_find_and_click_area(screen, '实战模拟室', '预备编队',
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击预备编队')
    @node_from(from_name='选择编队失败')
    @operation_node(name='选择编队')
    def choose_team(self) -> OperationRoundResult:
        screen = self.screenshot()

        area = self.ctx.screen_loader.get_area('实战模拟室', '预备出战')
        result = self.round_by_ocr(screen, '预备出战', area=area,
                                   color_range=[(240, 240, 240), (255, 255, 255)])
        if result.is_success:
            return self.round_success(result.status)

        team_list = self.ctx.team_config.team_list

        for target_team_idx in self.target_team_idx_list:
            if team_list is None or target_team_idx >= len(team_list):
                return self.round_fail('选择的预备编队下标错误 %s' % target_team_idx)

            target_team_name = team_list[target_team_idx].name

            ocr_map = self.ctx.ocr.run_ocr(screen)
            target_list = list(ocr_map.keys())
            best_match = difflib.get_close_matches(target_team_name, target_list, n=1)

            if best_match is None or len(best_match) == 0:
                return self.round_retry(wait=0.5)

            ocr_result: MatchResultList = ocr_map.get(best_match[0], None)
            if ocr_result is None or ocr_result.max is None:
                return self.round_retry(wait=0.5)

            to_click = ocr_result.max.center + Point(200, 0)
            self.ctx.controller.click(to_click)

            time.sleep(1)

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
        screen = self.screenshot()

        result = self.round_by_find_and_click_area(screen, '实战模拟室', '预备出战')
        if result.is_success:
            time.sleep(0.5)
            self.ctx.controller.mouse_move(ScreenNormalWorldEnum.UID.value.center)  # 点击后 移开鼠标 防止识别不到出战
            return self.round_success(result.status, wait=0.5)
        else:
            return self.round_retry(result.status, wait=1)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()

    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('img')
    print(ctx.ocr.run_ocr(screen))


if __name__ == '__main__':
    __debug()
