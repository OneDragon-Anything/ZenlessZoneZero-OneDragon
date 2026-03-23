from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.standalone.zzz_standalone_app_run_interface import (
    ZStandaloneAppRunInterface,
)


class ZStandaloneAppInterface(PivotNavigatorInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(
            self,
            object_name='standalone_interface',
            nav_text_cn='应用运行',
            nav_icon=FluentIcon.APPLICATION,
            parent=parent,
        )

    def create_sub_interface(self):
        self.add_sub_interface(ZStandaloneAppRunInterface(self.ctx))
