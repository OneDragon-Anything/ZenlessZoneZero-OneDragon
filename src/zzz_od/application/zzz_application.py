from collections.abc import Callable

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame


class ZApplication(Application):
    CLOUD_GAME_NOT_ENTERED_AREA_LIST: list[tuple[str, str]] = [
        ('云游戏', '国服PC云-点击空白区域关闭'),
        ('云游戏', '国服PC云-排队中'),
        ('云游戏', '国服PC云-开始游戏'),
        ('云游戏', '国服PC云-邦邦点快速队列'),
        ('云游戏', '国服PC云-普通队列'),
        ('云游戏', '国服PC云-切换窗口'),
        ('打开游戏', '点击进入游戏'),
    ]

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

    def handle_resume(self) -> None:
        self.ctx.controller.active_window()
        Application.handle_resume(self)

    def check_game_window(self) -> OperationRoundResult:
        """检查游戏窗口是否准备就绪，云游戏未进入时视为未就绪。"""
        if self.ctx.controller is None or not self.ctx.controller.is_game_window_ready:
            win_title = (
                ''
                if self.ctx.controller is None
                else self.ctx.controller.game_win.win_title
            )
            return self.round_fail(f'未打开游戏窗口 {win_title}')

        if not self.ctx.game_account_config.is_cloud_game:
            return self.check_game_initialized()

        screen = self.screenshot()
        for screen_name, area_name in ZApplication.CLOUD_GAME_NOT_ENTERED_AREA_LIST:
            result = self.round_by_find_area(screen, screen_name, area_name)
            if result.is_success:
                return self.round_fail(result.status)

        return self.check_game_initialized()
