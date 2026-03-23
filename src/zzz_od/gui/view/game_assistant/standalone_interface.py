from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.game_assistant.standalone_task_run_interface import (
    StandaloneTaskRunInterface,
)


class StandaloneInterface(PivotNavigatorInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(
            self,
            object_name='standalone_interface',
            nav_text_cn='独立运行',
            nav_icon=FluentIcon.APPLICATION,
            parent=parent,
        )

    def create_sub_interface(self):
        self.add_sub_interface(StandaloneTaskRunInterface(self.ctx))
