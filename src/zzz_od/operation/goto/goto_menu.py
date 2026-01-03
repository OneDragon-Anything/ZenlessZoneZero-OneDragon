from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.zzz_operation import ZOperation


class GotoMenu(ZOperation):

    def __init__(self, ctx: ZContext):
        """
        需要保证在任何情况下调用，都能前往菜单
        :param ctx:
        """
        ZOperation.__init__(self, ctx, op_name=gt('前往菜单'))
        self._tried_open_menu_click: bool = False
        self._tried_open_menu_esc: bool = False
        self._pending_menu_open_rounds: int = 0

    @operation_node(name='画面识别', is_start_node=True, node_max_retry_times=60)
    def check_screen_and_run(self) -> OperationRoundResult:

        mini_map = self.ctx.world_patrol_service.cut_mini_map(self.last_screenshot)
        if mini_map.play_mask_found:
            # 在大世界时优先用固定入口打开菜单：
            # 1) 先尝试点击菜单按钮（部分配置需要 ALT+Click）
            # 2) 若仍在大世界（小地图仍可见），再补一次 ESC 兜底
            if not self._tried_open_menu_click:
                self._tried_open_menu_click = True
                self._pending_menu_open_rounds = 3
                self.ctx.controller.active_window()
                self.round_by_click_area('大世界-普通', '按钮-菜单')
                return self.round_retry(status='尝试打开菜单-点击', wait=1)

            if not self._tried_open_menu_esc:
                self._tried_open_menu_esc = True
                self._pending_menu_open_rounds = 3
                self.ctx.controller.active_window()
                self.ctx.controller.keyboard_controller.tap('esc')
                return self.round_retry(status='尝试打开菜单-ESC', wait=1)

            # 两种方式都试过仍在大世界，重置后再来一轮（避免卡死在 WAIT）
            self._tried_open_menu_click = False
            self._tried_open_menu_esc = False
            return self.round_retry(status='仍在大世界，重试打开菜单', wait=1)

        result = self.round_by_goto_screen(screen=self.last_screenshot, screen_name='菜单', retry_wait=None)
        if result.is_success:
            return self.round_success(result.status)

        if (not result.is_fail  # fail是没有路径可以到达
                and self.ctx.screen_loader.current_screen_name is not None  # 能识别到当前画面 说明能打开菜单
        ):
            return self.round_wait(result.status, wait=1)

        if self._pending_menu_open_rounds > 0:
            self._pending_menu_open_rounds -= 1
            return self.round_retry(status='等待菜单载入', wait=1)

        # 到这里说明无法自动从当前画面前往菜单 就先统一返回大世界
        op = BackToNormalWorld(self.ctx)
        op_result = op.execute()
        if op_result.success:
            return self.round_retry(op_result.status, wait=1)
        else:
            # 大世界也没法返回的话 就不知道怎么去菜单了
            return self.round_fail(op_result.status)
