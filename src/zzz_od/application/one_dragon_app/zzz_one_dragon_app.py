from one_dragon.base.operation.application import application_const
from one_dragon.base.operation.one_dragon_app import OneDragonApp
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


def __debug():
    ctx = ZContext()
    # 加载配置
    ctx.init_async()
    # 异步更新免费代理
    ctx.async_update_gh_proxy()

    if ctx.env_config.auto_update:
        from one_dragon.utils.log_utils import log
        log.info('开始自动更新...')
        ctx.git_service.fetch_latest_code()

    app = ZOneDragonApp(ctx)
    app.execute()

    from one_dragon.base.config.one_dragon_config import AfterDoneOpEnum
    if ctx.one_dragon_config.after_done == AfterDoneOpEnum.SHUTDOWN.value.value:
        from one_dragon.utils import cmd_utils
        cmd_utils.shutdown_sys(60)
    elif ctx.one_dragon_config.after_done == AfterDoneOpEnum.CLOSE_GAME.value.value:
        ctx.controller.close_game()

    ctx.btn_listener.stop()


if __name__ == '__main__':
    __debug()
