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
        self.next_scanned_team_idx: int = 0
        self.scanned_team_idx_list: list[int] = []
        self.scanned_team_name_set: set[str] = set()
        self.shiyu_team_selected: bool = shiyu_target_list is None
        self.pending_select_button_center: Point | None = None
        self.pending_cancel_button_center: Point | None = None
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
        """
        分轮完成防卫战预备编队的扫描、评分与选择。

        扫描完成后先回到目标编队所在页面。游戏可能已有预选编队，
        此时需取消预选并等待原按钮恢复为 SELECT，避免直接选择失败。
        取消或选择后若持续无法确认状态，按节点重试上限失败退出，避免无限等待。
        每次点击后也要等待画面确认选中，再继续处理下一支编队。
        """
        if not self.shiyu_team_selected:
            scan_finished = self._scan_team_page(self.last_screenshot)
            log.info(
                '预备编队扫描结果:完成:%s 已扫描:%d 当前页:%d',
                scan_finished,
                len(self.scanned_team_idx_list),
                self.current_scroll_page,
            )
            if not scan_finished:
                log.info(
                    '预备编队扫描继续:向下拖动 页码:%d→%d',
                    self.current_scroll_page,
                    self.current_scroll_page + 1,
                )
                self._scroll_team_list(-1)
                self.current_scroll_page += 1
                return self.round_wait(
                    ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE,
                    wait=1,
                )
            if not self._select_shiyu_teams():
                return self.round_fail('预备编队不足以完成自动配队')
            self.shiyu_team_selected = True

        if self.pending_cancel_button_center is not None:
            ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
            if not self._is_select_button_visible(ocr_result_map):
                return self.round_retry(
                    '取消预选后未恢复SELECT',
                    wait=0.5,
                )
            log.info('预备编队取消完成:已恢复SELECT')
            self.pending_cancel_button_center = None
            return self.round_wait(
                ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE,
                wait=0.2,
            )

        if self.pending_select_button_center is not None:
            ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
            if not self._is_team_selected(ocr_result_map):
                return self.round_retry(
                    '选择预备编队后未确认选中状态',
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
            selected_button_mr = self._find_selected_button(ocr_result_map, team_name_mr)
            if selected_button_mr is None:
                return self.round_fail(f'当前编队未找到SELECT {target_team.name}')
            log.info('预备编队取消选择:队伍:%s 当前状态非SELECT', target_team.name)
            self.ctx.controller.click(
                team_name_mr.center + ChoosePredefinedTeam.TEAM_NAME_CLICK_OFFSET
            )
            self.pending_cancel_button_center = selected_button_mr.center
            return self.round_wait(
                ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE,
                wait=0.5,
            )

        log.info('预备编队选择:队伍:%s 已找到SELECT', target_team.name)
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
        """
        扫描当前页面的预备编队，返回是否应结束扫描。

        相邻页面会重复显示卡片，按队名去重。满员判断优先用核心技 X/Y(分母 = 队伍人数):
        X/3(3 人)或 1P/2P/3P ≥2 个则参选评分(1P/2P/3P 文字 OCR 易漏读、空位也保留标记,
        故 X/Y 为主、≥2 兜底)。0/0 或无头像无 X/Y 视为空队停止扫描。不满员 / 不可用的队伍
        不参与评分，但仍保留其游戏列表序号，避免后续有效队的翻页与点击位置错位。
        """
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
                    log.info(
                        '预备编队扫描卡位:列:%d 行:%d 未识别队名',
                        title_x,
                        title_y,
                    )
                    continue
                if team_name in self.scanned_team_name_set:
                    log.info(
                        '预备编队扫描卡位:列:%d 行:%d 队名:%s 已扫描，跳过',
                        title_x,
                        title_y,
                        team_name,
                    )
                    continue

                agent_list = self._recognize_team_agents(screen, team_name_mr)
                agent_slot_set = self._get_team_agent_slot_set(
                    ocr_result_map,
                    team_name_mr,
                )
                team_count_text = self._get_team_count_text(
                    ocr_result_map,
                    team_name_mr,
                )
                log.info(
                    '预备编队扫描卡位:列:%d 行:%d 队名:%s 代理人数量:%d 槽位:%s 核心技:%s',
                    title_x,
                    title_y,
                    team_name,
                    len(agent_list),
                    sorted(agent_slot_set),
                    team_count_text,
                )
                if len(agent_list) == 0 and (
                    team_count_text is None or team_count_text.endswith('/0')
                ):
                    log.info('预备编队扫描结束:队名:%s 队伍为空', team_name)
                    return True

                team_idx = self.next_scanned_team_idx
                if team_idx >= self.MAX_TEAM_COUNT:
                    log.info('预备编队扫描结束:已达到最大队伍数量:%d', self.MAX_TEAM_COUNT)
                    return True
                # 不可用的队伍不参与自动配队，但仍占用游戏列表中的位置。
                # 必须先递增真实序号，再跳过候选列表；否则后续有效队会错位。
                self.next_scanned_team_idx += 1
                self.scanned_team_name_set.add(team_name)

                # 可用(参选)判据(满足其一):
                # ① 核心技 X/3(分母 = 队伍人数,3 = 满员)—— 主判据,绕开 1P/2P/3P 文字 OCR 漏读;
                # ② 1P/2P/3P 识别到 ≥2 个 —— X/3 漏读时兜底(空位也保留 1P/2P/3P 标记,
                #    不满员队可能命中,由 select_teams 按评分 / 互斥排除)。
                is_available = (
                    team_count_text is not None and team_count_text.endswith('/3')
                ) or len(agent_slot_set) >= 2
                if not is_available:
                    log.info(
                        '预备编队不可用:序号:%d 队名:%s 核心技%s 槽位%s',
                        team_idx + 1,
                        team_name,
                        team_count_text,
                        sorted(agent_slot_set),
                    )
                    continue

                self.ctx.team_config.update_team_by_idx(team_idx, team_name, agent_list)
                self.scanned_team_idx_list.append(team_idx)
                log.info(
                    '预备编队 %d 名称:%s 代理人:%s',
                    team_idx + 1,
                    team_name,
                    [agent.agent_name for agent in agent_list],
                )

        scanned_count = self.next_scanned_team_idx
        scan_finished = scanned_count >= self.MAX_TEAM_COUNT
        if scan_finished:
            log.info('预备编队扫描结束:已扫描:%d', scanned_count)
        return scan_finished

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

    def _find_selected_button(
        self,
        ocr_result_map: dict[str, MatchResultList],
        team_name_mr: MatchResult,
    ) -> MatchResult | None:
        """查找当前卡片的已选状态，用于在缺少 SELECT 时先取消预选。"""
        candidate_list: list[MatchResult] = []
        for text, mr_list in ocr_result_map.items():
            if not self._is_selected_text(text.replace(' ', '').upper()):
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

    def _is_select_button_visible(
        self,
        ocr_result_map: dict[str, MatchResultList],
    ) -> bool:
        """确认取消后原按钮区域恢复 SELECT，避免误认其他卡片的 SELECT。"""
        if self.pending_cancel_button_center is None:
            return False

        center = self.pending_cancel_button_center
        for text, mr_list in ocr_result_map.items():
            if not text.replace(' ', '').upper().endswith('SELECT'):
                continue
            for mr in mr_list:
                if (
                    abs(mr.center.x - center.x)
                    <= ChoosePredefinedTeam.SELECT_BUTTON_FEEDBACK_HALF_WIDTH
                    and abs(mr.center.y - center.y)
                    <= ChoosePredefinedTeam.SELECT_BUTTON_FEEDBACK_HALF_HEIGHT
                ):
                    return True
        return False

    @staticmethod
    def _is_selected_text(normalized_text: str) -> bool:
        """统一已选按钮的 OCR 结果，仅在目标卡片的按钮区域内使用。"""
        return (
            normalized_text == 'SELECTED'
            or normalized_text == 'TEAM'
            or normalized_text.startswith('TEAM')
            or re.fullmatch(r'0\d', normalized_text) is not None  # 0 开头两位数:选中态编号 01-09(排除角色等级 60 等)
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
                if self._is_selected_text(normalized_text):
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

    def _get_team_agent_slot_set(
        self,
        ocr_result_map: dict[str, MatchResultList],
        team_name_mr: MatchResult,
    ) -> set[str]:
        """
        获取当前卡片识别到的代理人槽位标记。

        1P、2P、3P 任一缺失表示该队被禁用。角色头像仍可能被识别到，
        因此不能仅凭头像判断可用性；OCR 结果也必须限制在当前卡片范围内。
        """
        agent_rect = Rect(
            team_name_mr.left_top.x - 10,
            team_name_mr.left_top.y,
            team_name_mr.left_top.x + 800,
            team_name_mr.left_top.y + 250,
        )
        agent_slot_set: set[str] = set()
        for text, mr_list in ocr_result_map.items():
            normalized_text = text.replace(' ', '').upper()
            if normalized_text not in {'1P', '2P', '3P'}:
                continue
            for mr in mr_list:
                if (
                    mr.left_top.x >= agent_rect.x1
                    and mr.right_bottom.x <= agent_rect.x2
                    and mr.left_top.y >= agent_rect.y1
                    and mr.right_bottom.y <= agent_rect.y2
                ):
                    agent_slot_set.add(normalized_text)
        return agent_slot_set

    def _get_team_count_text(
        self,
        ocr_result_map: dict[str, MatchResultList],
        team_name_mr: MatchResult,
    ) -> str | None:
        """
        识别当前卡片的核心技激活 X/Y(分母 = 队伍人数,如 '3/3')。

        有 X/Y 说明这是一张有核心技激活进度的队伍卡(分母 = 角色数,3 = 满员)。
        用于配合 / 替代 1P/2P/3P 判断队伍是否完整(1P/2P/3P 文字 OCR 易漏读时兜底)。
        X/Y 在队名右上方(略高于队名),故 y 起点上移 30 以包含。
        """
        agent_rect = Rect(
            team_name_mr.left_top.x - 10,
            team_name_mr.left_top.y - 30,
            team_name_mr.left_top.x + 800,
            team_name_mr.left_top.y + 250,
        )
        for text, mr_list in ocr_result_map.items():
            normalized = text.replace(' ', '')
            # X/Y(含斜线,如 3/3);或 OCR 把斜线误识为 1 的连写(如 313=3/3、213=2/3、013=0/3)
            m = re.fullmatch(r'(\d+)/(\d+)', normalized)
            if m is None:
                m = re.fullmatch(r'(\d)1(\d)', normalized)
            if m is None:
                continue
            count_text = f'{m.group(1)}/{m.group(2)}'
            for mr in mr_list:
                if (
                    mr.left_top.x >= agent_rect.x1
                    and mr.right_bottom.x <= agent_rect.x2
                    and mr.left_top.y >= agent_rect.y1
                    and mr.right_bottom.y <= agent_rect.y2
                ):
                    return count_text
        return None

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
        """
        按固定坐标拖动列表。

        固定坐标避免鼠标停留位置影响翻页；向下扫描和向上回退使用相反方向，
        每次拖动对应 current_scroll_page 的一页变化。
        """
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
