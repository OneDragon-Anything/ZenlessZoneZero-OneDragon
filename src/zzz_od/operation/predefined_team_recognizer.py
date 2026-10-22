import re
from dataclasses import dataclass

from cv2.typing import MatLike

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResultList
from one_dragon.utils import cal_utils, str_utils
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.agent_template_matcher import (
    AgentTemplateMatchResult,
    match_team_agent_template,
)


@dataclass
class PredefinedTeamRecognition:
    """单张预备编队卡片的识别结果。"""

    team_name: str | None
    agent_match_result_list: list[AgentTemplateMatchResult]


TEAM_NAME_UI_TEXT_SET: frozenset[str] = frozenset(
    {'1P', '2P', '3P', 'TEAM', 'AGENT', 'BANGBOO', '60'}
)


def is_team_name_ui_text(text: str) -> bool:
    """判断 OCR 文本是否为卡片上的固定 UI 文本。"""
    normalized_text = str_utils.remove_whitespace(text).upper()
    if normalized_text in TEAM_NAME_UI_TEXT_SET or 'SELECT' in normalized_text:
        return True
    return re.fullmatch(r'\d+/\d+', normalized_text) is not None


def find_team_name(
    ocr_result_map: dict[str, MatchResultList],
    team_slot_rect: Rect,
) -> str | None:
    """在卡片顶部 70 像素内找面积最大的非 UI 文本。"""
    name_rect = Rect(
        team_slot_rect.x1,
        team_slot_rect.y1,
        team_slot_rect.x2,
        min(team_slot_rect.y1 + 70, team_slot_rect.y2),
    )
    target_name: str | None = None
    target_area = 0
    for text, mr_list in ocr_result_map.items():
        mr = mr_list.max
        if mr is None or is_team_name_ui_text(text):
            continue
        if (
            mr.left_top.x < name_rect.x1
            or mr.right_bottom.x > name_rect.x2
            or mr.left_top.y < name_rect.y1
            or mr.right_bottom.y > name_rect.y2
        ):
            continue
        if mr.rect.area > target_area:
            target_name = str_utils.remove_whitespace(text)
            target_area = mr.rect.area
    return target_name


def recognize_predefined_team(
    ctx: ZContext,
    screen: MatLike,
    ocr_result_map: dict[str, MatchResultList],
    team_slot_rect: Rect,
) -> PredefinedTeamRecognition:
    """识别一张卡片的队名和代理人，不依赖配置中的队名。"""
    avatar_rect = Rect(
        team_slot_rect.x1 - 10,
        team_slot_rect.y1,
        team_slot_rect.x1 + (team_slot_rect.width * 3 // 4),
        team_slot_rect.y2,
    )
    agent_mr_list = match_team_agent_template(ctx, screen, avatar_rect, None)
    agent_mr_list.sort(key=lambda mr: mr.left_top.x)

    filtered_mr_list: list[AgentTemplateMatchResult] = []
    for current_mr in agent_mr_list:
        if not filtered_mr_list:
            filtered_mr_list.append(current_mr)
            continue
        previous_mr = filtered_mr_list[-1]
        if cal_utils.cal_overlap_percent(current_mr.rect, previous_mr.rect) < 0.7:
            filtered_mr_list.append(current_mr)
        elif current_mr.confidence > previous_mr.confidence:
            filtered_mr_list[-1] = current_mr

    return PredefinedTeamRecognition(
        team_name=find_team_name(ocr_result_map, team_slot_rect),
        agent_match_result_list=filtered_mr_list[:3],
    )
