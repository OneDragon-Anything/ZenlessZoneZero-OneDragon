from one_dragon_qt.widgets.segmented_setting_interface import SegmentedSettingInterface
from zzz_od.context.zzz_context import ZContext


class WorldPatrolCombinedSettingInterface(SegmentedSettingInterface):

    def __init__(self, ctx: ZContext, parent=None):
        from zzz_od.gui.view.world_patrol.world_patrol_large_map_recorder_interface import (
            LargeMapRecorderInterface,
        )
        from zzz_od.gui.view.world_patrol.world_patrol_route_list_interface import (
            WorldPatrolRouteListInterface,
        )
        from zzz_od.gui.view.world_patrol.world_patrol_route_recorder_interface import (
            WorldPatrolRouteRecorderInterface,
        )
        from zzz_od.gui.view.world_patrol.world_patrol_setting_interface import (
            WorldPatrolSettingInterface,
        )

        SegmentedSettingInterface.__init__(
            self,
            object_name='world_patrol_combined_setting',
            nav_text_cn='锄大地配置',
            sub_interfaces=[
                WorldPatrolSettingInterface(ctx),
                WorldPatrolRouteListInterface(ctx),
                LargeMapRecorderInterface(ctx),
                WorldPatrolRouteRecorderInterface(ctx),
            ],
            parent=parent,
        )
