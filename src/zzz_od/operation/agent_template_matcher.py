from cv2.typing import MatLike

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.utils import cv2_utils
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent, AgentEnum


class AgentTemplateMatchResult(MatchResult):
    """预备编队头像模板的匹配结果。"""

    def __init__(
        self,
        match_result: MatchResult,
        agent: Agent,
        template_id: str,
    ) -> None:
        MatchResult.__init__(
            self,
            match_result.confidence,
            match_result.x,
            match_result.y,
            match_result.w,
            match_result.h,
            match_result.template_scale,
            agent,
        )
        self.template_id: str = template_id


def match_team_agent_template(
    ctx: ZContext,
    screen: MatLike,
    rect: Rect,
    agent_list_str: list[str] | None = None
) -> list[AgentTemplateMatchResult]:
    part = cv2_utils.crop_image_only(screen, rect)
    source_kp, source_desc = cv2_utils.feature_detect_and_compute(part)

    agent_mr_list: list[AgentTemplateMatchResult] = []
    for agent_enum in AgentEnum:
        agent: Agent = agent_enum.value
        if agent_list_str is not None and agent.agent_id not in agent_list_str:
            continue
        for template_id in agent.template_id_list:
            template = ctx.template_loader.get_template('predefined_team', f'avatar_{template_id}')
            if template is None:
                continue
            template_kp, template_desc = template.features
            mr = cv2_utils.feature_match_for_one(
                source_kp,
                source_desc,
                template_kp,
                template_desc,
                template_width=template.raw.shape[1],
                template_height=template.raw.shape[0],
                knn_distance_percent=0.5,
            )

            if mr is None:
                continue

            mr.add_offset(rect.left_top)
            agent_mr_list.append(
                AgentTemplateMatchResult(mr, agent, template_id)
            )
    return agent_mr_list
