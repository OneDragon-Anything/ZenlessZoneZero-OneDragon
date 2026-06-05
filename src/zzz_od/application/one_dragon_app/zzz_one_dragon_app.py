from contextlib import suppress

from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.one_dragon_app import OneDragonApp
from one_dragon.base.operation.operation_base import OperationResult
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame
from zzz_od.operation.enter_game.switch_account import SwitchAccount


class ZOneDragonApp(OneDragonApp, ZApplication):

    def __init__(self, ctx: ZContext):
        op_to_enter_game = OpenAndEnterGame(ctx)
        op_to_switch_account = SwitchAccount(ctx)

        ZApplication.__init__(
            self,
            ctx=ctx,
            app_id=application_const.ONE_DRAGON_APP_ID,
        )
        OneDragonApp.__init__(
            self,
            ctx=ctx,
            op_to_enter_game=op_to_enter_game,
            op_to_switch_account=op_to_switch_account,
        )

    def after_operation_done(self, result: OperationResult) -> None:
        """一条龙运行结束，递增运行计数"""
        super().after_operation_done(result)
        if result.success:
            with suppress(Exception):
                self.ctx.user_stats.increment_one_dragon()


def __debug():
    ctx = ZContext()
    ctx.init()
    ctx.run_context.start_running()
    app = ZOneDragonApp(ctx)
    app.execute()

if __name__ == '__main__':
    __debug()
