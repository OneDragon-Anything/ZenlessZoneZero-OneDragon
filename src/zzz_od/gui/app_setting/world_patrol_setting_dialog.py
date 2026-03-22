from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from one_dragon_qt.widgets.app_setting.pivot_navi_dialog import PivotNavigatorDialog
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

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class WorldPatrolSettingDialog(PivotNavigatorDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        PivotNavigatorDialog.__init__(self, ctx=ctx, title="锄大地配置", parent=parent)
        self.ctx: ZContext = ctx

    @cached_property
    def setting_interface(self) -> WorldPatrolSettingInterface:
        return WorldPatrolSettingInterface(self.ctx)

    def create_sub_interface(self):
        self.add_sub_interface(self.setting_interface)
        self.add_sub_interface(WorldPatrolRouteListInterface(self.ctx))
        self.add_sub_interface(LargeMapRecorderInterface(self.ctx))
        self.add_sub_interface(WorldPatrolRouteRecorderInterface(self.ctx))

    def show_by_group(self, group_id: str, parent: QWidget) -> None:
        self.setting_interface.set_group_id(group_id)
        super().show_by_group(group_id=group_id, parent=parent)
