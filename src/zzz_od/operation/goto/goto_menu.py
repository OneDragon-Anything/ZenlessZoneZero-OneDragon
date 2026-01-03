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
        初始化 GotoMenu 操作并设置用于控制打开菜单尝试的内部状态。
        
        初始化以下内部字段以管理尝试打开菜单的流程：_tried_open_menu_click、_tried_open_menu_esc、_pending_menu_open_rounds。
        
        Parameters:
            ctx (ZContext): 操作上下文，用于访问运行时服务和资源。
        """
        ZOperation.__init__(self, ctx, op_name=gt('前往菜单'))
        self._tried_open_menu_click: bool = False
        self._tried_open_menu_esc: bool = False
        self._pending_menu_open_rounds: int = 0

    @operation_node(name='画面识别', is_start_node=True, node_max_retry_times=60)
    def check_screen_and_run(self) -> OperationRoundResult:

        """
        尝试将游戏界面切换到“菜单”画面，负责在大世界场景使用固定入口打开菜单并在失败时回退处理。
        
        根据当前截图判断是否处于大世界：若是，优先按预定顺序尝试通过点击菜单按钮和按 ESC 打开菜单（每种方式仅尝试一次并在需要时设置等待轮次）；若不在大世界则尝试通过导航器识别并前往“菜单”画面；在等待加载超时后回退到大世界流程并根据回退结果决定重试或失败。
        
        Returns:
            OperationRoundResult: 表示本轮操作结果的对象，可能为重试（带等待）、等待（等待画面识别）、成功（已到达菜单）或失败（无法进入菜单且回退失败），并包含用于用户可见的状态消息。
        """
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