from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from zzz_od.gui.dialog.world_patrol_setting_dialog import WorldPatrolSettingDialog

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext

class SharedDialogManager:

    def __init__(self, ctx):
        self.ctx: ZContext = ctx
        self._world_patrol_setting_dialog: WorldPatrolSettingDialog | None = None

    def show_world_patrol_setting_dialog(
        self,
        parent: QWidget,
        group_id: str,
    ):
        if self._world_patrol_setting_dialog is None:
            self._world_patrol_setting_dialog = WorldPatrolSettingDialog(ctx=self.ctx, parent=parent)

        self._world_patrol_setting_dialog.show_by_group(
            group_id=group_id,
            parent=parent,
        )