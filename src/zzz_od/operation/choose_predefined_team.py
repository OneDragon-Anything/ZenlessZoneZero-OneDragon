import re
import time
from typing import TYPE_CHECKING

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cal_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent
from zzz_od.operation.agent_template_matcher import match_team_agent_template
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum

if TYPE_CHECKING:
    from zzz_od.application.shiyu_defense.shiyu_defense_team_utils import (
        DefensePhaseTeamInfo,
    )


class ChoosePredefinedTeam(ZOperation):

    STATUS_CONTINUE_CHOOSE: str = '继续选择'
    STATUS_CHOOSE_FINISHED: str = '选择完成'
    STATUS_TEAM_LIST_READY: str = '已在预备编队列表'
    STATUS_CHOOSE_FINISHED_WITHOUT_CONFIRM: str = '选择完成且不确认'

    TEAM_NAME_CLICK_OFFSET: Point = Point(300, 0)
    SELECT_BUTTON_FEEDBACK_HALF_WIDTH: int = 160
    SELECT_BUTTON_FEEDBACK_HALF_HEIGHT: int = 120
    TEAM_SCROLL_STEP: int = 4
    TEAM_DRAG_START: Point = Point(300, 715)
    TEAM_DRAG_END: Point = Point(300, 150)
    TEAM_COLUMN_COUNT: int = 2
    TEAM_ROW_COUNT: int = 3
    MAX_TEAM_COUNT: int = 20
    CARD_TITLE_X_LIST: list[int] = [150, 970]
    CARD_TITLE_Y_LIST: list[int] = [115, 398, 680]
    CARD_TITLE_WIDTH: int = 300
    CARD_TITLE_HEIGHT: int = 70

    def __init__(
        self,
        ctx: ZContext,
        target_team_idx_list: list[int] | None = None,
        shiyu_target_list: list['DefensePhaseTeamInfo'] | None = None,
        shiyu_click_target_list: list['DefensePhaseTeamInfo'] | None = None,
        start_at_team_list: bool = False,
        finish_without_confirm: bool = False,
    ):
        """
        在预备编队界面选择队伍
        """
        ZOperation.__init__(
            self,
            ctx,
            op_name=f"{gt('选择预备编队')} {target_team_idx_list}",
            need_check_game_win=not start_at_team_list,
        )

        self.target_team_idx_list: list[int] = (
            [] if target_team_idx_list is None else target_team_idx_list
        )
        self.shiyu_target_list: list[DefensePhaseTeamInfo] | None = shiyu_target_list
        self.shiyu_click_target_list: list[DefensePhaseTeamInfo] | None = (
            shiyu_click_target_list
        )
        self.current_target_idx: int = 0
        self.current_scroll_page: int = 0
        self.scanned_team_idx_list: list[int] = []
        self.scanned_team_name_set: set[str] = set()
        self.shiyu_team_selected: bool = shiyu_target_list is None
        self.pending_select_button_center: Point | None = None
        self.start_at_team_list: bool = start_at_team_list
        self.finish_without_confirm: bool = finish_without_confirm

    @operation_node(name='画面识别', node_max_retry_times=10, is_start_node=True)
    def check_screen(self) -> OperationRoundResult:
        if self.start_at_team_list:
            return self.round_success(ChoosePredefinedTeam.STATUS_TEAM_LIST_READY)

        result = self.round_by_find_area(self.last_screenshot, '实战模拟室', '预备编队')
        if result.is_success:
            return self.round_success(result.status)
        return self.round_retry(result.status, wait=1)

    @node_from(from_name='画面识别', status='预备编队')
    @operation_node(name='点击预备编队')
    def click_team(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(
            self.last_screenshot,
            '实战模拟室',
            '预备编队',
            success_wait=1,
            retry_wait=1,
        )

    @node_from(from_name='点击预备编队')
    @node_from(from_name='画面识别', status=STATUS_TEAM_LIST_READY)
    @node_from(from_name='选择编队', status=STATUS_CONTINUE_CHOOSE)
    @operation_node(name='选择编队')
    def choose_team(self) -> OperationRoundResult:
        if not self.shiyu_team_selected:
            if not self._scan_team_page(self.last_screenshot):
                self._scroll_team_list(-1)
                self.current_scroll_page += 1
                return self.round_wait(
                    ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE,
                    wait=1,
                )
            if not self._select_shiyu_teams():
                return self.round_fail('预备编队不足以完成自动配队')
            self.shiyu_team_selected = True

        if self.pending_select_button_center is not None:
            ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
            if not self._is_team_selected(ocr_result_map):
                return self.round_wait(
                    ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE,
                    wait=0.5,
                )
            self.pending_select_button_center = None
            self.current_target_idx += 1
            return self.round_wait(
                ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE,
                wait=0.2,
            )

        if self.current_target_idx >= len(self.target_team_idx_list):
            if self.finish_without_confirm:
                return self.round_success(
                    ChoosePredefinedTeam.STATUS_CHOOSE_FINISHED_WITHOUT_CONFIRM
                )

            result = self.round_by_find_area(
                self.last_screenshot,
                '实战模拟室',
                '预备出战',
            )
            if result.is_success:
                return self.round_success(ChoosePredefinedTeam.STATUS_CHOOSE_FINISHED)
            return self.round_retry(result.status, wait=1)

        target_team_idx = self.target_team_idx_list[self.current_target_idx]
        if target_team_idx < 0:
            return self.round_fail(f'选择的预备编队下标错误 {target_team_idx}')

        target_scroll_page = target_team_idx // self.TEAM_SCROLL_STEP
        if target_scroll_page > self.current_scroll_page:
            self._scroll_team_list(-1)
            self.current_scroll_page += 1
            return self.round_wait(ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE, wait=1)
        if target_scroll_page < self.current_scroll_page:
            self._scroll_team_list(1)
            self.current_scroll_page -= 1
            return self.round_wait(ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE, wait=1)

        target_team = self.ctx.team_config.get_team_by_idx(target_team_idx)
        if target_team is None:
            return self.round_fail(f'选择的预备编队下标错误 {target_team_idx}')

        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        team_name_mr = self._find_exact_team_name(ocr_result_map, target_team.name)
        if team_name_mr is None:
            return self.round_fail(f'当前页未找到编队 {target_team.name}')

        select_button_mr = self._find_select_button(ocr_result_map, team_name_mr)
        if select_button_mr is None:
            return self.round_fail(f'当前编队未找到+ SELECT {target_team.name}')

        self.ctx.controller.click(
            team_name_mr.center + ChoosePredefinedTeam.TEAM_NAME_CLICK_OFFSET
        )
        self.pending_select_button_center = select_button_mr.center
        return self.round_wait(ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE, wait=0.5)

    @node_from(from_name='选择编队', status=STATUS_CHOOSE_FINISHED)
    @operation_node(name='选择编队确认')
    def click_confirm(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(
            self.last_screenshot,
            '实战模拟室',
            '预备出战',
        )
        if result.is_success:
            time.sleep(0.5)
            self.ctx.controller.mouse_move(ScreenNormalWorldEnum.UID.value.center)
            return self.round_success(result.status, wait=0.5)
        return self.round_retry(result.status, wait=1)

    def _scan_team_page(self, screen: MatLike) -> bool:
        ocr_result_map = self.ctx.ocr.run_ocr(screen)

        for title_y in self.CARD_TITLE_Y_LIST:
            for title_x in self.CARD_TITLE_X_LIST:
                team_name, team_name_mr = self._find_team_name(
                    ocr_result_map,
                    Rect(
                        title_x,
                        title_y,
                        title_x + self.CARD_TITLE_WIDTH,
                        title_y + self.CARD_TITLE_HEIGHT,
                    ),
                )
                if team_name is None or team_name_mr is None:
                    continue
                if team_name in self.scanned_team_name_set:
                    continue

                agent_list = self._recognize_team_agents(screen, team_name_mr)
                if len(agent_list) == 0:
                    return True

                team_idx = len(self.scanned_team_idx_list)
                if team_idx >= self.MAX_TEAM_COUNT:
                    return True

                self.ctx.team_config.update_team_by_idx(team_idx, team_name, agent_list)
                self.scanned_team_name_set.add(team_name)
                self.scanned_team_idx_list.append(team_idx)
                log.info(
                    '预备编队 %d 名称:%s 代理人:%s',
                    team_idx + 1,
                    team_name,
                    [agent.agent_name for agent in agent_list],
                )

        return len(self.scanned_team_idx_list) >= self.MAX_TEAM_COUNT

    def _select_shiyu_teams(self) -> bool:
        if self.shiyu_target_list is None:
            return False

        from zzz_od.application.shiyu_defense.shiyu_defense_team_utils import (
            select_teams,
        )

        result_list = select_teams(
            self.ctx,
            self.shiyu_target_list,
            self.scanned_team_idx_list,
        )
        if len(result_list) != len(self.shiyu_target_list):
            return False

        for target, result in zip(self.shiyu_target_list, result_list, strict=True):
            target.team_idx = result.team_idx
            target.score = result.score

        click_target_list = (
            self.shiyu_target_list
            if self.shiyu_click_target_list is None
            else self.shiyu_click_target_list
        )
        self.target_team_idx_list = [target.team_idx for target in click_target_list]
        return all(team_idx >= 0 for team_idx in self.target_team_idx_list)

    def _find_exact_team_name(
        self,
        ocr_result_map: dict[str, MatchResultList],
        target_team_name: str,
    ) -> MatchResult | None:
        target_name = target_team_name.replace(' ', '')
        for text, mr_list in ocr_result_map.items():
            if text.replace(' ', '') != target_name or mr_list.max is None:
                continue
            return mr_list.max
        return None

    def _find_select_button(
        self,
        ocr_result_map: dict[str, MatchResultList],
        team_name_mr: MatchResult,
    ) -> MatchResult | None:
        candidate_list: list[MatchResult] = []
        for text, mr_list in ocr_result_map.items():
            if not text.replace(' ', '').upper().endswith('SELECT'):
                continue
            for mr in mr_list:
                x_offset = mr.center.x - team_name_mr.center.x
                y_offset = mr.center.y - team_name_mr.center.y
                if 300 <= x_offset <= 850 and 40 <= y_offset <= 250:
                    candidate_list.append(mr)

        if len(candidate_list) == 0:
            return None
        return min(
            candidate_list,
            key=lambda mr: (
                abs(mr.center.x - team_name_mr.center.x - 650)
                + abs(mr.center.y - team_name_mr.center.y - 130)
            ),
        )

    def _is_team_selected(
        self,
        ocr_result_map: dict[str, MatchResultList],
    ) -> bool:
        if self.pending_select_button_center is None:
            return False

        center = self.pending_select_button_center
        for text, mr_list in ocr_result_map.items():
            normalized_text = text.replace(' ', '').upper()
            for mr in mr_list:
                if (
                    abs(mr.center.x - center.x)
                    > ChoosePredefinedTeam.SELECT_BUTTON_FEEDBACK_HALF_WIDTH
                    or abs(mr.center.y - center.y)
                    > ChoosePredefinedTeam.SELECT_BUTTON_FEEDBACK_HALF_HEIGHT
                ):
                    continue
                if normalized_text.endswith('SELECT'):
                    return False
                if (
                    normalized_text == 'SELECTED'
                    or normalized_text == 'TEAM'
                    or normalized_text.startswith('TEAM')
                    or re.fullmatch(r'\d{2}', normalized_text) is not None
                ):
                    return True

        return False

    def _find_team_name(
        self,
        ocr_result_map: dict[str, MatchResultList],
        title_rect: Rect,
    ) -> tuple[str | None, MatchResult | None]:
        target_name: str | None = None
        target_mr: MatchResult | None = None

        for text, mr_list in ocr_result_map.items():
            if mr_list.max is None:
                continue
            mr = mr_list.max
            if (
                mr.left_top.x < title_rect.x1
                or mr.right_bottom.x > title_rect.x2
                or mr.left_top.y < title_rect.y1
                or mr.right_bottom.y > title_rect.y2
            ):
                continue
            if target_mr is None or mr.rect.area > target_mr.rect.area:
                target_name = text
                target_mr = mr

        return target_name, target_mr

    def _recognize_team_agents(
        self,
        screen: MatLike,
        team_name_mr: MatchResult,
    ) -> list[Agent]:
        avatar_rect = Rect(
            team_name_mr.left_top.x - 10,
            team_name_mr.left_top.y,
            team_name_mr.left_top.x + 800,
            team_name_mr.left_top.y + 250,
        )
        agent_mr_list = match_team_agent_template(self.ctx, screen, avatar_rect, None)
        agent_mr_list.sort(key=lambda mr: mr.left_top.x)

        filtered_mr_list: list[MatchResult] = []
        for current_mr in agent_mr_list:
            if len(filtered_mr_list) == 0:
                filtered_mr_list.append(current_mr)
                continue

            previous_mr = filtered_mr_list[-1]
            if cal_utils.cal_overlap_percent(current_mr.rect, previous_mr.rect) < 0.7:
                filtered_mr_list.append(current_mr)
            elif current_mr.confidence > previous_mr.confidence:
                filtered_mr_list[-1] = current_mr

        return [mr.data for mr in filtered_mr_list]

    def _scroll_team_list(self, direction: int) -> None:
        if direction < 0:
            self.ctx.controller.drag_to(
                start=ChoosePredefinedTeam.TEAM_DRAG_START,
                end=ChoosePredefinedTeam.TEAM_DRAG_END,
                duration=0.5,
            )
        else:
            self.ctx.controller.drag_to(
                start=ChoosePredefinedTeam.TEAM_DRAG_END,
                end=ChoosePredefinedTeam.TEAM_DRAG_START,
                duration=0.5,
            )
