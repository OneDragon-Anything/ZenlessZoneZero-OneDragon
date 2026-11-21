from collections.abc import Callable

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.enter_game import EnterGame
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame


class ZApplication(Application):

    def __init__(self, ctx: ZContext, app_id: str,
                 node_max_retry_times: int = 1,
                 op_name: str | None = None,
                 timeout_seconds: float = -1,
                 op_callback: Callable[[OperationResult], None] | None = None,
                 need_check_game_win: bool = True,
                 op_to_enter_game: Operation | None = None,
                 run_record: AppRunRecord | None = None,
                 ):
        self.ctx: ZContext = ctx
        if op_to_enter_game is None:
            op_to_enter_game = OpenAndEnterGame(ctx)
        Application.__init__(
            self,
            ctx=ctx,
            app_id=app_id,
            node_max_retry_times=node_max_retry_times,
            op_name=op_name,
            timeout_seconds=timeout_seconds,
            op_callback=op_callback,
            need_check_game_win=need_check_game_win,
            op_to_enter_game=op_to_enter_game,
            run_record=run_record,
        )

    def check_game_window(self) -> OperationRoundResult:
        """检查游戏窗口是否就绪；若处于登录画面则自动执行进入游戏流程。"""
        result = Application.check_game_window(self)
        if not result.is_success:
            return result

        self.ctx.controller.active_window()
        _, screen = self.ctx.controller.screenshot()
        if EnterGame.is_login_screen(self.ctx, screen):
            log.info('检测到当前处于登录画面，开始进入游戏')
            op = EnterGame(self.ctx)
            return self.round_by_op_result(op.execute())

        return result

    def handle_resume(self) -> None:
        self.ctx.controller.active_window()
        Application.handle_resume(self)
