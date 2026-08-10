from collections.abc import Callable

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.application_run_record import AppRunRecord
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.back_to_normal_world import BackToNormalWorld
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame


def _create_back_to_normal_world(ctx: ZContext) -> Operation:
    """创建默认的成功后操作。"""
    return BackToNormalWorld(ctx)


class ZApplication(Application):

    def __init__(self, ctx: ZContext, app_id: str,
                 node_max_retry_times: int = 1,
                 op_name: str | None = None,
                 timeout_seconds: float = -1,
                 op_callback: Callable[[OperationResult], None] | None = None,
                 need_check_game_win: bool = True,
                 op_to_enter_game: Operation | None = None,
                 run_record: AppRunRecord | None = None,
                 after_success_operation_factory: Callable[[ZContext], Operation] | None = _create_back_to_normal_world,
                 ) -> None:
        """初始化绝区零应用，并设置成功后的通用操作工厂。"""
        self.ctx: ZContext = ctx
        self.after_success_operation_factory: Callable[[ZContext], Operation] | None = after_success_operation_factory
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
        """恢复运行时激活游戏窗口。"""
        self.ctx.controller.active_window()
        Application.handle_resume(self)

    def after_operation_done(self, result: OperationResult) -> None:
        """应用成功时执行后置操作，再按最终结果更新记录和发送通知。"""
        if result.success and self.after_success_operation_factory is not None:
            after_result = self.after_success_operation_factory(self.ctx).execute()
            if not after_result.success:
                reason = after_result.status or '未知原因'
                result.success = False
                result.status = f'成功后操作失败: {reason}'

        Application.after_operation_done(self, result)
