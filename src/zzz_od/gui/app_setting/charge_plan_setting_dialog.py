from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from one_dragon_qt.widgets.app_setting.pivot_navi_dialog import PivotNavigatorDialog
from zzz_od.gui.view.one_dragon.charge_plan_interface import ChargePlanInterface

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class ChargePlanSettingDialog(PivotNavigatorDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        PivotNavigatorDialog.__init__(self, ctx=ctx, title="体力计划配置", parent=parent)
        self.ctx: ZContext = ctx

    @cached_property
    def charge_plan_interface(self) -> ChargePlanInterface:
        return ChargePlanInterface(self.ctx)

    def create_sub_interface(self):
        self.add_sub_interface(self.charge_plan_interface)
