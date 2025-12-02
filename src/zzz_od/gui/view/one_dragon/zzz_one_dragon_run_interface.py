from one_dragon.base.operation.application import application_const
from one_dragon_qt.view.one_dragon.one_dragon_run_interface import OneDragonRunInterface
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
        else:
            self.show_info_bar(
                title=f'{app_name} 暂不支持设置',
                content='',
                duration=3000,
            )
