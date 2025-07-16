from qfluentwidgets import FluentIcon

from one_dragon_qt.view.setting.setting_custom_interface import SettingCustomInterface
from one_dragon_qt.view.setting.setting_env_interface import SettingEnvInterface
from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.setting.setting_game_interface import SettingGameInterface
from zzz_od.gui.view.setting.setting_yolo_interface import SettingYoloInterface
from zzz_od.gui.view.setting.zzz_setting_instance_interface import ZSettingInstanceInterface



class AppSettingInterface(PivotNavigatorInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(self, object_name='app_setting_interface', parent=parent,
                                         nav_text_cn='设置', nav_icon=FluentIcon.SETTING) # 增加一个空格以避免被强制本地化渲染

    def create_sub_interface(self):
        """
        创建下面的子页面
        :return:
        """
        self.add_sub_interface(SettingGameInterface(ctx=self.ctx))
        self.add_sub_interface(SettingYoloInterface(ctx=self.ctx))
        self.add_sub_interface(SettingEnvInterface(ctx=self.ctx))
        self.add_sub_interface(SettingCustomInterface(ctx=self.ctx))
