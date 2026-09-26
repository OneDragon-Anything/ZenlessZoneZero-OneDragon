from collections.abc import Callable
from typing import cast

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame

_DEFAULT_AFTER_OPERATION = cast(Operation, object())


class ZApplication(Application):

    def __init__(self, ctx: ZContext, app_id: str,
                 node_max_retry_times: int = 1,
                 op_name: str | None = None,
                 timeout_seconds: float = -1,
                 op_callback: Callable[[OperationResult], None] | None = None,
                 need_check_game_win: bool = True,
                 op_to_enter_game: Operation | None = None,
                 run_record: AppRunRecord | None = None,
                 op_before: Operation | None = None,
                 op_after: Operation | None = _DEFAULT_AFTER_OPERATION,
                 ) -> None:
        """初始化绝区零应用，并把前置、后置操作挂到流程图。"""
        self.ctx: ZContext = ctx
        if op_to_enter_game is None:
            op_to_enter_game = OpenAndEnterGame(ctx)
        if op_after is _DEFAULT_AFTER_OPERATION:
            op_after = BackToNormalWorld(ctx)
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
            op_before=op_before,
            op_after=op_after,
        )

    def handle_resume(self) -> None:
        """恢复运行时激活游戏窗口。"""
        self.ctx.controller.active_window()
        Application.handle_resume(self)
