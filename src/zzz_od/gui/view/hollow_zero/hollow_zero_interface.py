from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.hollow_zero.withered_domain_challenge_config_interface import WitheredDomainChallengeConfigInterface
from zzz_od.gui.view.hollow_zero.withered_domain_run_interface import WitheredDomainRunInterface
from zzz_od.gui.view.hollow_zero.lost_void_challenge_config_interface import LostVoidChallengeConfigInterface
from zzz_od.gui.view.hollow_zero.lost_void_run_interface import LostVoidRunInterface


class HollowZeroInterface(PivotNavigatorInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(self, object_name='hollow_interface', parent=parent,
                                         nav_text_cn='零号空洞', nav_icon=FluentIcon.IOT)

    def create_sub_interface(self):
        """
        创建下面的子页面
        :return:
        """
        self.add_sub_interface(WitheredDomainRunInterface(self.ctx))
        self.add_sub_interface(WitheredDomainChallengeConfigInterface(self.ctx))
        self.add_sub_interface(LostVoidRunInterface(self.ctx))
        self.add_sub_interface(LostVoidChallengeConfigInterface(self.ctx))
