import difflib
import time

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum


def match_team_name(target: str, candidates: list[str]) -> str | None:
    """
    在OCR候选文本里找目标编队名

    规则: 去空白后先精确匹配; 再用 difflib 模糊匹配(>=0.6)兜底OCR错字,
    但排除「非数字部分相同、数字部分不同」的候选 —— 那是另一支编队。
    例如编队列表一页只显示约6个编队, 目标「编队8」不在当前页时,
    直接 get_close_matches 会把「编队1」按 0.67 相似度当成命中 → 点错编队,
    且永远不会触发翻页(翻页只在完全没匹配时走)。

    :param target: 目标编队名
    :param candidates: OCR识别出的全部文本
    :return: 命中的候选原文 找不到返回 None
    """
    def _clean(s: str) -> str:
        return ''.join(s.split())

    def _digits(s: str) -> str:
        return ''.join(c for c in s if c.isdigit())

    def _non_digits(s: str) -> str:
        return ''.join(c for c in s if not c.isdigit())

    target_clean = _clean(target)
    best_key: str | None = None
    best_ratio: float = 0.0
    for cand in candidates:
        cand_clean = _clean(cand)
        if cand_clean == target_clean:
            return cand
        if (_non_digits(cand_clean) == _non_digits(target_clean)
                and _digits(cand_clean) != _digits(target_clean)):
            # 同前缀不同编号 = 另一支编队 不允许模糊命中
            continue
        ratio = difflib.SequenceMatcher(None, target_clean, cand_clean).ratio()
        if ratio >= 0.6 and ratio > best_ratio:
            best_ratio = ratio
            best_key = cand
    return best_key


class ChoosePredefinedTeam(ZOperation):

    TEAM_SCROLL_STEP: int = 4

    def __init__(self, ctx: ZContext, target_team_idx_list: list[int]):
        """
        在出战画面使用
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name=f"{gt('选择预备编队')} {target_team_idx_list}")

        self.target_team_idx_list: list[int] = target_team_idx_list
        self.scroll_page_count: int = 0
        # 预备编队默认打开在第一页，因此这里记录最多需要向下翻几页。
        # 一次下滑后，列表实际会前进 4 个编队。
        self.max_scroll_page_count: int = max(
            [
                target_team_idx // self.TEAM_SCROLL_STEP
                for target_team_idx in target_team_idx_list
                if target_team_idx >= 0
            ],
            default=0,
        )

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
    @node_from(from_name='尝试查找编队')
    @operation_node(name='选择编队')
    def choose_team(self) -> OperationRoundResult:
        area = self.ctx.screen_loader.get_area('实战模拟室', '预备出战')
        result = self.round_by_ocr(self.last_screenshot, '预备出战', area=area,
                                   color_range=[[240, 240, 240], [255, 255, 255]])
        if result.is_success:
            return self.round_success(result.status)

        team_list = self.ctx.team_config.team_list

        for target_team_idx in self.target_team_idx_list:
            if team_list is None or target_team_idx >= len(team_list):
                return self.round_fail(f'选择的预备编队下标错误 {target_team_idx}')

            target_team_name = team_list[target_team_idx].name

            ocr_map = self.ctx.ocr.run_ocr(self.last_screenshot)
            best_match = match_team_name(target_team_name, list(ocr_map.keys()))

            if best_match is None:
                return self.round_fail(f'当前页未找到编队 {target_team_name}')

            ocr_result: MatchResultList = ocr_map.get(best_match, None)
            if ocr_result is None or ocr_result.max is None:
                return self.round_fail(f'当前页未找到编队 {target_team_name}')

            to_click = ocr_result.max.center + Point(200, 0)
            self.ctx.controller.click(to_click)

            time.sleep(0.5)

        return self.round_wait(wait=1)

    @node_from(from_name='选择编队', success=False)
    @operation_node(name='尝试查找编队')
    def try_find_team(self) -> OperationRoundResult:
        self.scroll_page_count += 1
        if self.scroll_page_count > self.max_scroll_page_count:
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


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.init_ocr()

    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('img')
    print(ctx.ocr.run_ocr(screen))


if __name__ == '__main__':
    __debug()
