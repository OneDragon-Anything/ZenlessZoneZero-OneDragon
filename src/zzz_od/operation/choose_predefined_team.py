import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cal_utils, cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent
from zzz_od.operation.agent_template_matcher import (
    AgentTemplateMatchResult,
    match_team_agent_template,
)
from zzz_od.operation.zzz_operation import ZOperation
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum

if TYPE_CHECKING:
    from zzz_od.application.shiyu_defense.shiyu_defense_team_utils import (
        DefensePhaseTeamInfo,
    )


@dataclass
class TeamAgentScanResult:
    """预备编队中一个代理人的扫描结果。"""

    agent: Agent
    is_dim: bool
    match_result: AgentTemplateMatchResult


class ChoosePredefinedTeam(ZOperation):

    STATUS_CONTINUE_CHOOSE: str = '继续选择'
    STATUS_CHOOSE_FINISHED: str = '选择完成'
    STATUS_TEAM_LIST_READY: str = '已在预备编队列表'
    STATUS_CHOOSE_FINISHED_WITHOUT_CONFIRM: str = '选择完成且不确认'

    SELECT_BUTTON_FEEDBACK_HALF_WIDTH: int = 160
    SELECT_BUTTON_FEEDBACK_HALF_HEIGHT: int = 120
    DISABLED_AVATAR_BRIGHTNESS_RATIO: float = 0.7
    TEAM_SCROLL_STEP: int = 4
    TEAM_SLOT_COUNT: int = 6
    TEAM_DRAG_START: Point = Point(300, 715)
    TEAM_DRAG_END: Point = Point(300, 150)
    MAX_TEAM_COUNT: int = 20

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
        self.disabled_team_count: int = 0
        self.unrecognized_team_member_count: int = 0
        self.scan_started: bool = False
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
            if not self.scan_started:
                log.info('预备编队扫描开始')
                self.scan_started = True

            scan_finished = self._scan_team_page(self.last_screenshot)
            if not scan_finished:
                log.debug(
                    '预备编队扫描继续:当前页:%d 下一页:%d 有效:%d',
                    self.current_scroll_page,
                    self.current_scroll_page + 1,
                    len(self.scanned_team_idx_list),
                )
                self._scroll_team_list(-1)
                self.current_scroll_page += 1
                return self.round_wait(
                    ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE,
                    wait=1,
                )
            log.info(
                '预备编队扫描完成:有效:%d 禁用:%d 人数识别失败:%d',
                len(self.scanned_team_idx_list),
                self.disabled_team_count,
                self.unrecognized_team_member_count,
            )
            if not self._select_shiyu_teams():
                return self.round_fail('预备编队不足以完成自动配队')
            self.shiyu_team_selected = True

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

        current_page_start_team_idx = (
            self.current_scroll_page * self.TEAM_SCROLL_STEP
        )
        current_page_end_team_idx = (
            current_page_start_team_idx + self.TEAM_SLOT_COUNT - 1
        )
        if target_team_idx > current_page_end_team_idx:
            self._scroll_team_list(-1)
            self.current_scroll_page += 1
            return self.round_wait(ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE, wait=1)
        if target_team_idx < current_page_start_team_idx:
            self._scroll_team_list(1)
            self.current_scroll_page -= 1
            return self.round_wait(ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE, wait=1)

        target_team = self.ctx.team_config.get_team_by_idx(target_team_idx)
        if target_team is None:
            return self.round_fail(f'选择的预备编队下标错误 {target_team_idx}')
        team_slot_rect = self._get_team_slot_rect_by_idx(
            target_team_idx - current_page_start_team_idx
        )

        if self.pending_cancel_button_center is not None:
            ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
            if self._is_team_slot_disabled(
                self.last_screenshot,
                ocr_result_map,
                target_team.name,
                team_slot_rect,
            ):
                return self.round_fail(f'预备编队已禁用，停止选择 {target_team.name}')
            if not self._is_select_button_visible(ocr_result_map):
                return self.round_retry(
                    '取消预选后未恢复SELECT',
                    wait=0.5,
                )
            log.debug('预备编队取消预选已确认:队伍:%s', target_team.name)
            self.pending_cancel_button_center = None
            return self.round_wait(
                ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE,
                wait=0.2,
            )

        if self.pending_select_button_center is not None:
            ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
            if self._is_team_slot_disabled(
                self.last_screenshot,
                ocr_result_map,
                target_team.name,
                team_slot_rect,
            ):
                return self.round_fail(f'预备编队已禁用，停止选择 {target_team.name}')
            if not self._is_team_selected(ocr_result_map):
                return self.round_retry(
                    '选择预备编队后未确认选中状态',
                    wait=0.5,
                )
            log.info(
                '预备编队已选:队伍:%s 序号:%d',
                target_team.name,
                target_team_idx + 1,
            )
            self.pending_select_button_center = None
            self.current_target_idx += 1
            return self.round_wait(
                ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE,
                wait=0.2,
            )

        ocr_result_map = self.ctx.ocr.run_ocr(self.last_screenshot)
        team_name, _ = self._find_team_name(
            ocr_result_map,
            team_slot_rect,
        )
        if team_name is None:
            return self.round_fail(f'当前页未识别到预备编队 {target_team_idx + 1}')
        if target_team.name != team_name:
            log.debug(
                '预备编队名称更新:序号:%d 原名称:%s 新名称:%s',
                target_team_idx + 1,
                target_team.name,
                team_name,
            )
            self.ctx.team_config.update_team_name_by_idx(target_team_idx, team_name)
            target_team.name = team_name

        if self._is_team_slot_disabled(
            self.last_screenshot,
            ocr_result_map,
            team_name,
            team_slot_rect,
        ):
            return self.round_fail(f'预备编队已禁用，停止选择 {team_name}')

        select_button_mr = self._find_select_button(ocr_result_map, team_slot_rect)
        if select_button_mr is None:
            selected_button_mr = self._find_selected_button(
                ocr_result_map,
                team_slot_rect,
            )
            if selected_button_mr is None:
                return self.round_fail(f'当前编队未找到SELECT {target_team.name}')
            log.info('预备编队取消预选:队伍:%s', target_team.name)
            self.ctx.controller.click(selected_button_mr.center)
            self.pending_cancel_button_center = selected_button_mr.center
            return self.round_wait(
                ChoosePredefinedTeam.STATUS_CONTINUE_CHOOSE,
                wait=0.5,
            )

        log.info(
            '预备编队选择:队伍:%s 序号:%d',
            target_team.name,
            target_team_idx + 1,
        )
        self.ctx.controller.click(select_button_mr.center)
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
            log.info('预备编队选择完成:已点击预备出战')
            time.sleep(0.5)
            self.ctx.controller.mouse_move(ScreenNormalWorldEnum.UID.value.center)
            return self.round_success(result.status, wait=0.5)
        return self.round_retry(result.status, wait=1)

    def _scan_team_page(self, screen: MatLike) -> bool:
        """
        扫描当前页面的预备编队，返回是否应结束扫描。

        相邻页面会重复显示卡片，按队名去重。X/Y 的分母 Y 表示队伍代理人数，
        用于限制写入配置的代理人数量；例如单人队的第 2 个位置可能是邦布，不能因
        识别到后续头像而写入额外代理人。禁用必须同时满足 1P、2P、3P 标记不完整，
        且缺失槽位对应的代理人头像变暗。空队停止扫描；不可用的队伍仍保留游戏列表序号，
        有效队的翻页与点击位置错位。
        """
        ocr_result_map = self.ctx.ocr.run_ocr(screen)

        for card_idx in range(self.TEAM_SLOT_COUNT):
            team_slot_rect = self._get_team_slot_rect_by_idx(card_idx)
            team_name, _ = self._find_team_name(
                ocr_result_map,
                team_slot_rect,
            )
            if team_name is None:
                log.debug('预备编队扫描卡位:%d 未识别队名', card_idx + 1)
                continue
            if team_name in self.scanned_team_name_set:
                log.debug(
                    '预备编队扫描卡位:%d 队名:%s 已扫描，跳过',
                    card_idx + 1,
                    team_name,
                )
                continue

            agent_scan_result_list = self._recognize_team_agents(
                screen,
                team_slot_rect,
            )
            agent_list = [result.agent for result in agent_scan_result_list]
            agent_slot_set = self._get_team_agent_slot_set(
                ocr_result_map,
                team_slot_rect,
            )
            team_member_count = self._get_team_member_count(
                ocr_result_map,
                team_slot_rect,
            )
            log.debug(
                '预备编队扫描卡位:%d 队名:%s 代理人数量:%d 槽位:%s 队伍人数:%s',
                card_idx + 1,
                team_name,
                len(agent_list),
                sorted(agent_slot_set),
                team_member_count,
            )
            if team_member_count == 0 or (
                len(agent_list) == 0 and team_member_count is None
            ):
                log.debug('预备编队扫描结束:队名:%s 队伍为空', team_name)
                return True

            team_idx = self.next_scanned_team_idx
            if team_idx >= self.MAX_TEAM_COUNT:
                log.debug('预备编队扫描结束:已达到最大队伍数量:%d', self.MAX_TEAM_COUNT)
                return True
            # 不可用的队伍不参与自动配队，但仍占用游戏列表中的位置。
            # 必须先递增真实序号，再跳过候选列表；否则后续有效队会错位。
            self.next_scanned_team_idx += 1
            self.scanned_team_name_set.add(team_name)

            if team_member_count is None:
                self.ctx.team_config.update_team_name_by_idx(team_idx, team_name)
                self.unrecognized_team_member_count += 1
                log.warning(
                    '预备编队跳过:序号:%d 队名:%s 未识别队伍人数',
                    team_idx + 1,
                    team_name,
                )
                continue

            is_disabled = self._is_team_disabled(
                team_name,
                agent_slot_set,
                team_member_count,
                agent_scan_result_list,
            )
            if is_disabled:
                self.ctx.team_config.update_team_name_by_idx(team_idx, team_name)
                self.disabled_team_count += 1
                log.debug(
                    '预备编队禁用:序号:%d 队名:%s 代理人槽位不完整:%s 且头像变暗',
                    team_idx + 1,
                    team_name,
                    sorted(agent_slot_set),
                )
                continue

            team_member_list = agent_list[:team_member_count]
            self.ctx.team_config.update_team_by_idx(
                team_idx,
                team_name,
                team_member_list,
            )
            self.scanned_team_idx_list.append(team_idx)
            log.debug(
                '预备编队扫描有效:序号:%d 名称:%s 代理人:%s',
                team_idx + 1,
                team_name,
                [agent.agent_name for agent in team_member_list],
            )

        scanned_count = self.next_scanned_team_idx
        scan_finished = scanned_count >= self.MAX_TEAM_COUNT
        if scan_finished:
            log.debug('预备编队扫描结束:已扫描:%d', scanned_count)
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

    def _get_team_slot_rect_by_idx(self, card_idx: int) -> Rect:
        """返回当前页第 ``card_idx`` 张编队卡片区域。"""
        area = self.ctx.screen_loader.get_area('编队选择', f'编队槽位{card_idx}')
        if area is None:
            raise RuntimeError(f'未配置编队槽位{card_idx}')
        return area.rect

    def _get_select_mark_rect(self, team_slot_rect: Rect) -> Rect:
        """返回当前编队卡片所在列的选择标记区域。"""
        left_area = self.ctx.screen_loader.get_area('编队选择', '选择标记左')
        right_area = self.ctx.screen_loader.get_area('编队选择', '选择标记右')
        if left_area is None or right_area is None:
            raise RuntimeError('未配置编队选择标记区域')
        return min(
            [left_area, right_area],
            key=lambda area: abs(area.center.x - team_slot_rect.center.x),
        ).rect

    @staticmethod
    def _is_match_result_in_rect(match_result: MatchResult, rect: Rect) -> bool:
        return (
            match_result.left_top.x >= rect.x1
            and match_result.right_bottom.x <= rect.x2
            and match_result.left_top.y >= rect.y1
            and match_result.right_bottom.y <= rect.y2
        )

    def _find_select_button(
        self,
        ocr_result_map: dict[str, MatchResultList],
        team_slot_rect: Rect,
    ) -> MatchResult | None:
        select_mark_rect = self._get_select_mark_rect(team_slot_rect)
        candidate_list: list[MatchResult] = []
        for text, mr_list in ocr_result_map.items():
            if not text.replace(' ', '').upper().endswith('SELECT'):
                continue
            candidate_list.extend(
                mr
                for mr in mr_list
                if self._is_match_result_in_rect(mr, select_mark_rect)
            )

        if len(candidate_list) == 0:
            return None
        return min(
            candidate_list,
            key=lambda mr: abs(mr.center.y - team_slot_rect.center.y),
        )

    def _find_selected_button(
        self,
        ocr_result_map: dict[str, MatchResultList],
        team_slot_rect: Rect,
    ) -> MatchResult | None:
        """查找当前卡片的已选状态，用于在缺少 SELECT 时先取消预选。"""
        select_mark_rect = self._get_select_mark_rect(team_slot_rect)
        candidate_list: list[MatchResult] = []
        for text, mr_list in ocr_result_map.items():
            if not self._is_selected_text(text.replace(' ', '').upper()):
                continue
            candidate_list.extend(
                mr
                for mr in mr_list
                if self._is_match_result_in_rect(mr, select_mark_rect)
            )

        if len(candidate_list) == 0:
            return None
        return min(
            candidate_list,
            key=lambda mr: abs(mr.center.y - team_slot_rect.center.y),
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
        """判断 OCR 文本是否为选中态标记。"""
        return normalized_text == 'TEAM' or normalized_text.endswith('SELECTED')

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
        team_slot_rect: Rect,
    ) -> tuple[str | None, MatchResult | None]:
        target_name: str | None = None
        target_mr: MatchResult | None = None

        for text, mr_list in ocr_result_map.items():
            if mr_list.max is None:
                continue
            mr = mr_list.max
            if (
                mr.left_top.x < team_slot_rect.x1
                or mr.right_bottom.x > team_slot_rect.x2
                or mr.left_top.y < team_slot_rect.y1
                or mr.right_bottom.y > team_slot_rect.y2
            ):
                continue
            if target_mr is None or mr.rect.area > target_mr.rect.area:
                target_name = str_utils.remove_whitespace(text)
                target_mr = mr

        return target_name, target_mr

    def _is_agent_avatar_dim(
        self,
        screen: MatLike,
        agent_mr: AgentTemplateMatchResult,
    ) -> bool:
        """判断代理人头像是否低于对应模板原图亮度的阈值。"""
        template = self.ctx.template_loader.get_template(
            'predefined_team',
            f'avatar_{agent_mr.template_id}',
        )
        if template is None or template.raw is None:
            log.warning(
                '预备编队头像亮度:代理人:%s 模板:%s 未找到模板原图',
                agent_mr.data.agent_name,
                agent_mr.template_id,
            )
            return False

        avatar_image = cv2_utils.crop_image_only(screen, agent_mr.rect)
        if avatar_image.size == 0:
            log.warning(
                '预备编队头像亮度:代理人:%s 模板:%s 头像区域为空',
                agent_mr.data.agent_name,
                agent_mr.template_id,
            )
            return False
        template_image = cv2.resize(
            template.raw,
            (avatar_image.shape[1], avatar_image.shape[0]),
            interpolation=cv2.INTER_AREA,
        )
        avatar_brightness = float(
            np.mean(cv2.cvtColor(avatar_image, cv2.COLOR_RGB2HSV)[:, :, 2])
        )
        template_brightness = float(
            np.mean(cv2.cvtColor(template_image, cv2.COLOR_RGB2HSV)[:, :, 2])
        )
        brightness_ratio = (
            avatar_brightness / template_brightness
            if template_brightness > 0
            else None
        )
        is_dim = (
            brightness_ratio is not None
            and brightness_ratio <= self.DISABLED_AVATAR_BRIGHTNESS_RATIO
        )
        log.debug(
            '预备编队头像亮度:代理人:%s 模板:%s 实际:%.1f 模板:%.1f 比例:%.1f%% 阈值:%.1f%% 判暗:%s',
            agent_mr.data.agent_name,
            agent_mr.template_id,
            avatar_brightness,
            template_brightness,
            brightness_ratio * 100 if brightness_ratio is not None else 0,
            self.DISABLED_AVATAR_BRIGHTNESS_RATIO * 100,
            is_dim,
        )
        return is_dim

    def _get_team_agent_slot_set(
        self,
        ocr_result_map: dict[str, MatchResultList],
        team_slot_rect: Rect,
    ) -> set[str]:
        """
        获取当前卡片识别到的代理人槽位标记。

        `1P`、`2P`、`3P` 任一缺失是禁用的 OCR 信号；只有与该队代理人头像
        同时变暗时，才判为禁用。角色头像仍可能被识别到，因此 OCR 结果也必须限制
        在当前卡片范围内。
        """
        agent_slot_set: set[str] = set()
        for text, mr_list in ocr_result_map.items():
            normalized_text = text.replace(' ', '').upper()
            if normalized_text not in {'1P', '2P', '3P'}:
                continue
            for mr in mr_list:
                if self._is_match_result_in_rect(mr, team_slot_rect):
                    agent_slot_set.add(normalized_text)
        return agent_slot_set

    def _get_team_member_count(
        self,
        ocr_result_map: dict[str, MatchResultList],
        team_slot_rect: Rect,
    ) -> int | None:
        """获取当前卡片 X/Y 中表示代理人数的分母 Y。"""
        for text, mr_list in ocr_result_map.items():
            normalized = text.replace(' ', '')
            # OCR 可能把斜线误识为 1，例如 313 代表 3/3。
            m = re.fullmatch(r'(\d+)/(\d+)', normalized)
            if m is None:
                m = re.fullmatch(r'(\d)1(\d)', normalized)
            if m is None:
                continue
            for mr in mr_list:
                if self._is_match_result_in_rect(mr, team_slot_rect):
                    return int(m.group(2))
        return None

    def _is_team_disabled(
        self,
        team_name: str,
        agent_slot_set: set[str],
        team_member_count: int | None,
        agent_scan_result_list: list[TeamAgentScanResult],
    ) -> bool:
        """按缺失槽位与同序号代理人亮度判断预备编队是否禁用。"""
        team_agent_scan_result_list = (
            []
            if team_member_count is None
            else agent_scan_result_list[:team_member_count]
        )
        missing_slot_list: list[str] = []
        dim_missing_slot_list: list[str] = []
        if (
            team_member_count is not None
            and len(team_agent_scan_result_list) == team_member_count
        ):
            missing_slot_list = [
                f'{idx}P'
                for idx in range(1, team_member_count + 1)
                if f'{idx}P' not in agent_slot_set
            ]
            dim_missing_slot_list = [
                slot
                for slot in missing_slot_list
                if team_agent_scan_result_list[int(slot[0]) - 1].is_dim
            ]
        is_disabled = len(dim_missing_slot_list) > 0
        log.debug(
            '预备编队禁用判定:队名:%s 槽位:%s 队伍人数:%s 缺失槽位:%s 对应头像变暗:%s 结果:%s',
            team_name,
            sorted(agent_slot_set),
            team_member_count,
            missing_slot_list,
            dim_missing_slot_list,
            is_disabled,
        )
        return is_disabled

    def _is_team_slot_disabled(
        self,
        screen: MatLike,
        ocr_result_map: dict[str, MatchResultList],
        team_name: str,
        team_slot_rect: Rect,
    ) -> bool:
        """重新识别当前卡片，供点击和选中确认前拦截禁用队伍。"""
        agent_slot_set = self._get_team_agent_slot_set(
            ocr_result_map,
            team_slot_rect,
        )
        team_member_count = self._get_team_member_count(
            ocr_result_map,
            team_slot_rect,
        )
        agent_scan_result_list = self._recognize_team_agents(screen, team_slot_rect)
        return self._is_team_disabled(
            team_name,
            agent_slot_set,
            team_member_count,
            agent_scan_result_list,
        )

    def _recognize_team_agents(
        self,
        screen: MatLike,
        team_slot_rect: Rect,
    ) -> list[TeamAgentScanResult]:
        agent_mr_list = match_team_agent_template(
            self.ctx,
            screen,
            team_slot_rect,
            None,
        )
        agent_mr_list.sort(key=lambda mr: mr.left_top.x)

        filtered_mr_list: list[AgentTemplateMatchResult] = []
        for current_mr in agent_mr_list:
            if len(filtered_mr_list) == 0:
                filtered_mr_list.append(current_mr)
                continue

            previous_mr = filtered_mr_list[-1]
            if cal_utils.cal_overlap_percent(current_mr.rect, previous_mr.rect) < 0.7:
                filtered_mr_list.append(current_mr)
            elif current_mr.confidence > previous_mr.confidence:
                filtered_mr_list[-1] = current_mr

        return [
            TeamAgentScanResult(
                agent=mr.data,
                is_dim=self._is_agent_avatar_dim(screen, mr),
                match_result=mr,
            )
            for mr in filtered_mr_list
        ]

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
