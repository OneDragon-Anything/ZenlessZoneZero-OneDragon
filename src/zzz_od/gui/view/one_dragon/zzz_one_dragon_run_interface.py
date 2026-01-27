from one_dragon.base.operation.application import application_const
from one_dragon_qt.view.one_dragon.one_dragon_run_interface import OneDragonRunInterface
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.coffee import coffee_app_const
from zzz_od.application.drive_disc_dismantle import drive_disc_dismantle_const
from zzz_od.application.hollow_zero.lost_void import lost_void_const
from zzz_od.application.hollow_zero.withered_domain import withered_domain_const
from zzz_od.application.notorious_hunt import notorious_hunt_const
from zzz_od.application.random_play import random_play_const
from zzz_od.application.redemption_code import redemption_code_const
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
            help_url='https://one-dragon.com/zzz/zh/docs/feat_one_dragon.html'
        )

    def on_app_setting_clicked(self, app_id: str) -> None:
        group_id = application_const.DEFAULT_GROUP_ID
        app_name = self.ctx.run_context.get_application_name(app_id)
        if app_id == world_patrol_const.APP_ID:
            self.ctx.shared_dialog_manager.show_world_patrol_setting_dialog(
                parent=self,
                group_id=group_id
            )
        elif app_id == suibian_temple_const.APP_ID:
            self.ctx.shared_dialog_manager.show_suibian_temple_setting_dialog(
                parent=self,
                group_id=group_id
            )
        elif app_id == charge_plan_const.APP_ID:
            self.ctx.shared_dialog_manager.show_charge_plan_setting_dialog(
                parent=self,
                group_id=group_id
            )
        elif app_id == notorious_hunt_const.APP_ID:
            self.ctx.shared_dialog_manager.show_notorious_hunt_setting_dialog(
                parent=self,
                group_id=group_id
            )
        elif app_id == coffee_app_const.APP_ID:
            self.ctx.shared_dialog_manager.show_coffee_setting_dialog(
                parent=self,
                group_id=group_id
            )
        elif app_id == random_play_const.APP_ID:
            self.ctx.shared_dialog_manager.show_random_play_setting_dialog(
                parent=self,
                group_id=group_id
            )
        elif app_id == drive_disc_dismantle_const.APP_ID:
            self.ctx.shared_dialog_manager.show_drive_disc_dismantle_setting_dialog(
                parent=self,
                group_id=group_id
            )
        elif app_id == withered_domain_const.APP_ID:
            self.ctx.shared_dialog_manager.show_withered_domain_setting_dialog(
                parent=self,
                group_id=group_id
            )
        elif app_id == lost_void_const.APP_ID:
            self.ctx.shared_dialog_manager.show_lost_void_setting_dialog(
                parent=self,
                group_id=group_id
            )
        elif app_id == redemption_code_const.APP_ID:
            self.ctx.shared_dialog_manager.show_redemption_code_setting_dialog(
                parent=self,
                group_id=group_id
            )
        else:
            self.show_info_bar(
                title=f'{app_name} 暂不支持设置',
                content='',
                duration=3000,
            )
