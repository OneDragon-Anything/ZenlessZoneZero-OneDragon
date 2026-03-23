from collections.abc import Callable

from one_dragon_qt.view.one_dragon.one_dragon_run_interface import OneDragonRunInterface
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.coffee import coffee_app_const
from zzz_od.application.drive_disc_dismantle import drive_disc_dismantle_const
from zzz_od.application.hollow_zero.lost_void import lost_void_const
from zzz_od.application.hollow_zero.withered_domain import withered_domain_const
from zzz_od.application.intel_board import intel_board_const
from zzz_od.application.life_on_line import life_on_line_const
from zzz_od.application.notorious_hunt import notorious_hunt_const
from zzz_od.application.random_play import random_play_const
from zzz_od.application.redemption_code import redemption_code_const
from zzz_od.application.shiyu_defense import shiyu_defense_const
from zzz_od.application.suibian_temple import suibian_temple_const
from zzz_od.application.world_patrol import world_patrol_const
from zzz_od.context.zzz_context import ZContext


class ZOneDragonRunInterface(OneDragonRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        OneDragonRunInterface.__init__(
            self,
            ctx=ctx,
            parent=parent,
            help_url='https://one-dragon.com/zzz/zh/feat_one_dragon/quickstart.html',
        )

    def get_setting_dialog_map(self) -> dict[str, Callable]:
        mgr = self.ctx.app_setting_manager
        return {
            world_patrol_const.APP_ID:         mgr.show_world_patrol_setting,
            suibian_temple_const.APP_ID:       mgr.show_suibian_temple_setting,
            charge_plan_const.APP_ID:          mgr.show_charge_plan_setting,
            notorious_hunt_const.APP_ID:       mgr.show_notorious_hunt_setting,
            coffee_app_const.APP_ID:           mgr.show_coffee_setting,
            random_play_const.APP_ID:          mgr.show_random_play_setting_flyout,
            drive_disc_dismantle_const.APP_ID: mgr.show_drive_disc_dismantle_setting_flyout,
            withered_domain_const.APP_ID:      mgr.show_withered_domain_setting,
            lost_void_const.APP_ID:            mgr.show_lost_void_setting,
            redemption_code_const.APP_ID:      mgr.show_redemption_code_setting,
            life_on_line_const.APP_ID:         mgr.show_life_on_line_setting_flyout,
            shiyu_defense_const.APP_ID:        mgr.show_shiyu_defense_setting,
            intel_board_const.APP_ID:          mgr.show_intel_board_setting_flyout,
        }
