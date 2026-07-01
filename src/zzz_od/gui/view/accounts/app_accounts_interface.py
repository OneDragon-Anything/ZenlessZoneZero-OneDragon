from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.setting.zzz_setting_instance_interface import (
    ZSettingInstanceInterface,
)


class AccountsInterface(PivotNavigatorInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(self, object_name='app_accounts_interface', parent=parent,
                                         nav_text_cn='账户管理', nav_icon=FluentIcon.COPY)

    def create_sub_interface(self):
        """
        创建下面的子页面
        :return:
        """
        self.add_sub_interface(ZSettingInstanceInterface(ctx=self.ctx))
