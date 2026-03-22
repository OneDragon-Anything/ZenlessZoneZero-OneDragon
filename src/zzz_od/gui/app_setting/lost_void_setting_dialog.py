from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from one_dragon_qt.widgets.app_setting.pivot_navi_dialog import PivotNavigatorDialog
from zzz_od.gui.view.hollow_zero.lost_void_challenge_config_interface import (
    LostVoidChallengeConfigInterface,
)
from zzz_od.gui.view.hollow_zero.lost_void_setting_interface import (
    LostVoidSettingInterface,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class LostVoidSettingDialog(PivotNavigatorDialog):
    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        PivotNavigatorDialog.__init__(self, ctx=ctx, title="迷失之地配置", parent=parent)
        self.ctx: ZContext = ctx

    @cached_property
    def setting_interface(self) -> LostVoidSettingInterface:
        return LostVoidSettingInterface(self.ctx)

    def create_sub_interface(self):
        self.add_sub_interface(self.setting_interface)
        self.add_sub_interface(LostVoidChallengeConfigInterface(self.ctx))

    def show_by_group(self, group_id: str, parent: QWidget) -> None:
        self.setting_interface.set_group_id(group_id)
        super().show_by_group(group_id=group_id, parent=parent)
