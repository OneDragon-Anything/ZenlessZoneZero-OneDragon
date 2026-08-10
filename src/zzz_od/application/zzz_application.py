from collections.abc import Callable

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.utils.log_utils import log
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_settings.game_settings_profile_service import (
    GameSettingsProfileError,
)
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

    def execute(self) -> OperationResult:
        """执行绝区零应用，并由最外层应用切换游戏画质配置。"""
        try:
            profile_session_entered = self.ctx.game_settings_profile_service.enter()
        except GameSettingsProfileError as error:
            log.error("切换一条龙游戏画质配置失败: %s", error)
            return OperationResult(
                success=False,
                status=f"切换一条龙游戏画质配置失败: {error}",
            )

        restore_error: GameSettingsProfileError | None = None
        try:
            result = Application.execute(self)
        finally:
            if profile_session_entered:
                try:
                    self.ctx.game_settings_profile_service.exit()
                except GameSettingsProfileError as error:
                    restore_error = error
                    log.error("恢复正常游戏画质配置失败: %s", error)

        if restore_error is not None:
            return OperationResult(
                success=False,
                status=f"恢复正常游戏画质配置失败: {restore_error}",
            )
        return result

    def handle_resume(self) -> None:
        self.ctx.controller.active_window()
        Application.handle_resume(self)
