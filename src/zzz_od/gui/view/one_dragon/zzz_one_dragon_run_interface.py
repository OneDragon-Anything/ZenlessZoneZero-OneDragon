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
            help_url='https://one-dragon.com/zzz/zh/feat_one_dragon/quickstart.html'
        )

    def get_setting_dialog_map(self) -> dict[str, Callable]:
        mgr = self.ctx.shared_dialog_manager
        return {
            world_patrol_const.APP_ID:         mgr.show_world_patrol_setting_dialog,
            suibian_temple_const.APP_ID:       mgr.show_suibian_temple_setting_dialog,
            charge_plan_const.APP_ID:          mgr.show_charge_plan_setting_dialog,
            notorious_hunt_const.APP_ID:       mgr.show_notorious_hunt_setting_dialog,
            coffee_app_const.APP_ID:           mgr.show_coffee_setting_dialog,
            random_play_const.APP_ID:          mgr.show_random_play_setting_dialog,
            drive_disc_dismantle_const.APP_ID: mgr.show_drive_disc_dismantle_setting_dialog,
            withered_domain_const.APP_ID:      mgr.show_withered_domain_setting_dialog,
            lost_void_const.APP_ID:            mgr.show_lost_void_setting_dialog,
            redemption_code_const.APP_ID:      mgr.show_redemption_code_setting_dialog,
            life_on_line_const.APP_ID:         mgr.show_life_on_line_setting_dialog,
            shiyu_defense_const.APP_ID:        mgr.show_shiyu_defense_setting_dialog,
            intel_board_const.APP_ID:          mgr.show_intel_board_setting_flyout,
        }
