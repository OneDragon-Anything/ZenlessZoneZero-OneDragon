import time

import difflib
from cv2.typing import MatLike
from typing import List, ClassVar

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils import cv2_utils, str_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent, AgentEnum
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.goto.goto_menu import GotoMenu
from zzz_od.operation.transport import Transport
from zzz_od.operation.wait_normal_world import WaitNormalWorld


class TeamWrapper:

    def __init__(self, team_name: str, agent_list: List[Agent]):
        self.team_name: str = team_name
        self.agent_list: List[Agent] = agent_list


class PredefinedTeamChecker(ZApplication):

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx, app_id='predefined_team_checker',
            op_name=gt('预备编队角色识别'),
            retry_in_od=True,  # 传送落地有可能会歪 重试
        )

        self.scroll_times: int = 0  # 下滑次数

    @operation_node(name='前往菜单画面', is_start_node=True)
    def goto_menu(self) -> OperationRoundResult:
        op = GotoMenu(self.ctx)
        return self.round_by_op_result(op.execute())

    @node_from(from_name='前往菜单画面')
    @operation_node(name='前往更多功能画面')
    def goto_menu_more(self) -> OperationRoundResult:
        return self.round_by_goto_screen(screen_name='菜单-更多功能')

    @node_from(from_name='前往更多功能画面')
    @operation_node(name='点击预备编队')
    def click_predefined_team(self) -> OperationRoundResult:
        return self.round_by_find_and_click_area(screen_name='菜单-更多功能', area_name='按钮-预备编队',
                                                 until_not_find_all=[('菜单-更多功能', '按钮-预备编队')],
                                                 success_wait=1, retry_wait=1)

    @node_from(from_name='点击预备编队')
    @operation_node(name='识别编队角色')
    def check_team_members(self, screen: MatLike = None) -> OperationRoundResult:
        screen = self.screenshot()
        self.update_team_members(screen)

        if self.scroll_times == 0:
            drag_start = Point(self.ctx.controller.standard_width // 2, self.ctx.controller.standard_height // 2)
            drag_end = drag_start + Point(0, -500)
            self.ctx.controller.drag_to(start=drag_start, end=drag_end)
            self.scroll_times += 1
            return self.round_wait('继续识别', wait=1)
        else:
            return self.round_success()

    def update_team_members(self, screen: MatLike) -> None:
        result_team_list: List[TeamWrapper]
        ocr_result_map = self.ctx.ocr.run_ocr(screen)

        target_team_name_list: List[str] = []
        mr_list: List[MatchResult] = []
        for ocr_result, mrl in ocr_result_map.items():
            target_team_name_list.append(ocr_result)
            mr_list.append(mrl.max)

        for team in self.ctx.team_config.team_list:
            team_name = team.name

            # 需要先识别到队伍名称
            ocr_idx = str_utils.find_best_match_by_difflib(team_name, target_team_name_list)
            if ocr_idx is None or ocr_idx < 0:
                continue

            name_lt = mr_list[ocr_idx].left_top
            avatar_rect = Rect(
                name_lt.x - 10, name_lt.y,
                name_lt.x + 800, name_lt.y + 250
            )

            part = cv2_utils.crop_image_only(screen, avatar_rect)
            source_kp, source_desc = cv2_utils.feature_detect_and_compute(part)

            agent_mr_list: List[MatchResult] = []

            for agent_enum in AgentEnum:
                agent: Agent = agent_enum.value
                for template_id in agent.template_id_list:
                    template = self.ctx.template_loader.get_template('predefined_team', f'avatar_{template_id}')
                    if template is None:
                        continue
                    template_kp, template_desc = template.features
                    mr = cv2_utils.feature_match_for_one(
                        source_kp, source_desc, template_kp, template_desc,
                        template_width=template.raw.shape[1], template_height=template.raw.shape[0],
                        knn_distance_percent=0.5
                    )

                    if mr is None:
                        continue

                    agent_mr = mr
                    agent_mr.data = agent
                    agent_mr_list.append(agent_mr)

            if len(agent_mr_list) == 0:
                continue

            # agent_mr_list 按横坐标排序
            agent_mr_list.sort(key=lambda x: x.left_top.x)

            log.info(f'编队名称: {team_name} 识别代理人: {[i.data.agent_name for i in agent_mr_list]}')

            self.ctx.team_config.update_team_members(team_name, [i.data for i in agent_mr_list])


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.init_ocr()
    ctx.start_running()

    op = PredefinedTeamChecker(ctx)
    op.execute()


if __name__ == '__main__':
    __debug()