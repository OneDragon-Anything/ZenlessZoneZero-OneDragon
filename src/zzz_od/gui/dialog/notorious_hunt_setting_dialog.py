from __future__ import annotations

from typing import TYPE_CHECKING, List

from PySide6.QtWidgets import QWidget

from one_dragon_qt.widgets.column import Column
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanItem,
)
from zzz_od.application.notorious_hunt import notorious_hunt_const
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog
from zzz_od.gui.view.one_dragon.notorious_hunt_interface import ChargePlanCard

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class NotoriousHuntSettingDialog(AppSettingDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="恶名狩猎配置", parent=parent)

    def get_content_widget(self) -> QWidget:
        self.content_widget = Column()

        self.card_list: List[ChargePlanCard] = []
        self.last_empty_widget: QWidget = QWidget()

        return self.content_widget

    def update_plan_list_display(self):
        plan_list = self.config.plan_list

        if len(plan_list) > len(self.card_list):
            self.content_widget.remove_widget(self.last_empty_widget)

            while len(self.card_list) < len(plan_list):
                idx = len(self.card_list)
                card = ChargePlanCard(self.ctx, idx, self.config.plan_list[idx])
                card.changed.connect(self._on_plan_item_changed)

                self.card_list.append(card)
                self.content_widget.add_widget(card)

            self.content_widget.add_widget(self.last_empty_widget, stretch=1)

        for idx, plan in enumerate(plan_list):
            card = self.card_list[idx]
            card.init_with_plan(plan)

    def on_dialog_shown(self) -> None:
        super().on_dialog_shown()

        self.config = self.ctx.run_context.get_config(
            app_id=notorious_hunt_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )

        self.update_plan_list_display()

    def _on_plan_item_changed(self, idx: int, plan: ChargePlanItem) -> None:
        self.config.update_plan(idx, plan)
