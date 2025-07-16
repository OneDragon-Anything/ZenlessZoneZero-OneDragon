from qfluentwidgets import FluentIcon

from one_dragon_qt.view.setting.setting_custom_interface import SettingCustomInterface
from one_dragon_qt.view.setting.setting_env_interface import SettingEnvInterface
from one_dragon_qt.view.setting.setting_push_interface import SettingPushInterface
from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.setting.setting_game_interface import SettingGameInterface
from zzz_od.gui.view.setting.zzz_resource_download_interface import ZResourceDownloadInterface


class AppSettingInterface(PivotNavigatorInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(self, object_name='app_setting_interface', parent=parent,
                                         nav_text_cn='设置', nav_icon=FluentIcon.SETTING)

    def create_sub_interface(self):
        """
        创建下面的子页面
        :return:
        """
        self.add_sub_interface(SettingGameInterface(ctx=self.ctx))
        self.add_sub_interface(ZResourceDownloadInterface(ctx=self.ctx))
        self.add_sub_interface(SettingEnvInterface(ctx=self.ctx))
        self.add_sub_interface(SettingPushInterface(ctx=self.ctx))
        self.add_sub_interface(SettingCustomInterface(ctx=self.ctx))
