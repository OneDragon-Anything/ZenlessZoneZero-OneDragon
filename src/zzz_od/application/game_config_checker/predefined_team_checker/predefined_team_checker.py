from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from zzz_od.application.game_config_checker.predefined_team_checker import (
    predefined_team_checker_const,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import Agent
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.goto.goto_menu import GotoMenu
from zzz_od.operation.predefined_team_recognizer import recognize_predefined_team


class TeamWrapper:

    def __init__(self, team_name: str, agent_list: list[Agent]):
        self.team_name: str = team_name
        self.agent_list: list[Agent] = agent_list


class PredefinedTeamChecker(ZApplication):

    """预备编队角色识别:校准工具,识别预备编队的实际角色(切换队伍前核对)。非玩法。"""

    TEAM_SLOT_COUNT: int = 6
    TEAM_SCROLL_STEP: int = 4

    def __init__(self, ctx: ZContext):
        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=predefined_team_checker_const.APP_ID,
            op_name=predefined_team_checker_const.APP_NAME,
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
                                                 until_not_find_all=[('菜单-更多功能', '按钮-兑换码')],
                                                 success_wait=2, retry_wait=1)

    @node_from(from_name='点击预备编队')
    @operation_node(name='识别编队角色')
    def check_team_members(self) -> OperationRoundResult:
        self.update_team_members(self.last_screenshot)

        if self.scroll_times < 4:
            drag_start = Point(960, 715)
            drag_end = Point(960, 150)
            self.ctx.controller.drag_to(start=drag_start, end=drag_end)
            self.scroll_times += 1
            return self.round_wait('继续识别', wait=1)
        else:
            return self.round_success()

    def _get_team_slot_rect(self, card_idx: int) -> Rect | None:
        area = self.ctx.screen_loader.get_area('编队选择', f'编队槽位{card_idx}')
        return None if area is None else area.rect

    def update_team_members(self, screen: MatLike) -> None:
        ocr_result_map = self.ctx.ocr.run_ocr(screen)
        team_list = self.ctx.team_config.team_list
        page_start_idx = self.scroll_times * self.TEAM_SCROLL_STEP

        for card_idx in range(self.TEAM_SLOT_COUNT):
            team_idx = page_start_idx + card_idx
            if team_idx >= len(team_list):
                continue

            team_slot_rect = self._get_team_slot_rect(card_idx)
            if team_slot_rect is None:
                continue
            recognition = recognize_predefined_team(
                self.ctx,
                screen,
                ocr_result_map,
                team_slot_rect,
            )
            team_name = recognition.team_name
            agent_mr_list = recognition.agent_match_result_list
            if len(agent_mr_list) == 0:
                continue

            for raw_mr in agent_mr_list:
                log.debug(
                    '预备编队角色原始匹配:序号:%d 角色:%s 模板:%s 置信度:%.3f 坐标:%d,%d,%d,%d',
                    team_idx + 1,
                    raw_mr.data.agent_name,
                    raw_mr.template_id,
                    raw_mr.confidence,
                    raw_mr.left_top.x,
                    raw_mr.left_top.y,
                    raw_mr.right_bottom.x,
                    raw_mr.right_bottom.y,
                )

            agent_list = [mr.data for mr in agent_mr_list]
            log.info(
                '编队序号:%d 当前名称:%s 识别代理人:%s',
                team_idx + 1,
                team_name if team_name is not None else '<未识别>',
                [agent.agent_name for agent in agent_list],
            )
            self.ctx.team_config.update_team_by_idx(
                team_idx,
                team_name,
                agent_list,
            )

    @node_from(from_name='识别编队角色')
    @operation_node(name='成功后返回')
    def back_at_last(self) -> OperationRoundResult:
        op = BackToNormalWorld(self.ctx)
        return self.round_by_op_result(op.execute())


def __debug_update_team_members():
    ctx = ZContext()
    ctx.init()
    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('497657553-30334c5e-a162-460e-b797-e31e75f7b03b')
    op = PredefinedTeamChecker(ctx)
    op.update_team_members(screen)


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()

    op = PredefinedTeamChecker(ctx)
    op.execute()


if __name__ == '__main__':
    __debug_update_team_members()
