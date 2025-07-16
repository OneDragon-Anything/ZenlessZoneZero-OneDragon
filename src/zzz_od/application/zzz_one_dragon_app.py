from typing import List

from one_dragon.base.operation.one_dragon_app import OneDragonApp
from zzz_od.application.charge_plan.charge_plan_app import ChargePlanApp
from zzz_od.application.city_fund.city_fund_app import CityFundApp
from zzz_od.application.coffee.coffee_app import CoffeeApp
from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_app import DriveDiscDismantleApp
from zzz_od.application.email_app.email_app import EmailApp
from zzz_od.application.engagement_reward.engagement_reward_app import EngagementRewardApp
from zzz_od.application.hollow_zero.lost_void.lost_void_app import LostVoidApp
from zzz_od.application.hollow_zero.withered_domain.hollow_zero_app import HollowZeroApp
from zzz_od.application.life_on_line.life_on_line_app import LifeOnLineApp
from zzz_od.application.notorious_hunt.notorious_hunt_app import NotoriousHuntApp
from zzz_od.application.random_play.random_play_app import RandomPlayApp
from zzz_od.application.redemption_code.redemption_code_app import RedemptionCodeApp
from zzz_od.application.ridu_weekly.ridu_weekly_app import RiduWeeklyApp
from zzz_od.application.scratch_card.scratch_card_app import ScratchCardApp
from zzz_od.application.shiyu_defense.shiyu_defense_app import ShiyuDefenseApp
from zzz_od.application.suibian_temple.suibian_temple_app import SuibianTempleApp
from zzz_od.application.trigrams_collection.trigrams_collection_app import TrigramsCollectionApp
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.enter_game.open_and_enter_game import OpenAndEnterGame
from zzz_od.operation.enter_game.switch_account import SwitchAccount


class ZOneDragonApp(OneDragonApp, ZApplication):

    def __init__(self, ctx: ZContext):
        app_id = 'zzz_one_dragon'
        op_to_enter_game = OpenAndEnterGame(ctx)
        op_to_switch_account = SwitchAccount(ctx)

        ZApplication.__init__(self, ctx, app_id)
        OneDragonApp.__init__(self, ctx, app_id,
                              op_to_enter_game=op_to_enter_game,
                              op_to_switch_account=op_to_switch_account)

    def get_app_list(self) -> List[ZApplication]:
        from zzz_od.application.notify.notify_app import NotifyApp
        return [
            RedemptionCodeApp(self.ctx),
            RandomPlayApp(self.ctx),
            ScratchCardApp(self.ctx),
            TrigramsCollectionApp(self.ctx),
            ChargePlanApp(self.ctx),
            CoffeeApp(self.ctx),
            NotoriousHuntApp(self.ctx),
            EngagementRewardApp(self.ctx),
            HollowZeroApp(self.ctx),
            LostVoidApp(self.ctx),
            ShiyuDefenseApp(self.ctx),
            SuibianTempleApp(self.ctx),
            CityFundApp(self.ctx),
            RiduWeeklyApp(self.ctx),
            EmailApp(self.ctx),
            DriveDiscDismantleApp(self.ctx),
            LifeOnLineApp(self.ctx),
            NotifyApp(self.ctx),
        ]


def __debug():
    ctx = ZContext()
    # 加载配置
    ctx.init_by_config()

    # 异步加载OCR
    ctx.async_init_ocr()

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