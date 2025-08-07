from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.pivot_navi_interface import PivotNavigatorInterface
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.world_patrol.world_patrol_large_map_recorder_interface import LargeMapRecorderInterface
from zzz_od.gui.view.world_patrol.world_patrol_route_list_interface import WorldPatrolRouteListInterface
from zzz_od.gui.view.world_patrol.world_patrol_route_recorder_interface import WorldPatrolRouteRecorderInterface
from zzz_od.gui.view.world_patrol.world_patrol_run_interface import WorldPatrolRunInterface


class WorldPatrolInterface(PivotNavigatorInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        PivotNavigatorInterface.__init__(self, object_name='world_patrol_interface', parent=parent,
                                         nav_text_cn='锄大地', nav_icon=FluentIcon.ROTATE)

    def create_sub_interface(self):
        """
        创建下面的子页面
        """
        self.add_sub_interface(WorldPatrolRunInterface(self.ctx))
        self.add_sub_interface(WorldPatrolRouteListInterface(self.ctx))
        self.add_sub_interface(LargeMapRecorderInterface(self.ctx))
        self.add_sub_interface(WorldPatrolRouteRecorderInterface(self.ctx))