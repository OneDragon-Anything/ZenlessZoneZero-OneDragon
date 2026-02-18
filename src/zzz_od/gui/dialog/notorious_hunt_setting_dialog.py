from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.draggable_list import DraggableList
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanItem,
)
from zzz_od.application.notorious_hunt import notorious_hunt_const
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog
from zzz_od.gui.view.one_dragon.notorious_hunt_interface import NotoriousHuntCard

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class NotoriousHuntSettingDialog(AppSettingDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="恶名狩猎配置", parent=parent)

    def get_content_widget(self) -> QWidget:
        self.content_widget = Column()

        # 创建可拖动的列表容器
        self.drag_list = DraggableList()
        self.drag_list.order_changed.connect(self._on_order_changed)
        self.content_widget.add_widget(self.drag_list)

        self.card_list: list[NotoriousHuntCard] = []

        return self.content_widget

    def update_plan_list_display(self) -> None:
        plan_list = self.config.plan_list

        if len(plan_list) > len(self.card_list):
            # 需要添加新的卡片
            while len(self.card_list) < len(plan_list):
                idx = len(self.card_list)
                card = NotoriousHuntCard(self.ctx, idx, self.config.plan_list[idx])
                card.changed.connect(self._on_plan_item_changed)
                card.move_top.connect(self._on_plan_item_move_top)

                self.card_list.append(card)
                self.drag_list.add_list_item(card)

        elif len(plan_list) < len(self.card_list):
            # 需要移除多余的卡片
            while len(self.card_list) > len(plan_list):
                self.drag_list.remove_item(len(self.card_list) - 1)
                self.card_list.pop(-1)

        # 更新所有卡片的显示
        for idx, plan in enumerate(plan_list):
            self.card_list[idx].update_item(plan, idx)

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

    def _on_plan_item_move_top(self, idx: int) -> None:
        self.config.move_top(idx)
        self.update_plan_list_display()

    def _on_order_changed(self, new_data_list: list[ChargePlanItem]) -> None:
        """
        拖拽改变顺序后的回调

        Args:
            new_data_list: 新顺序的数据列表
        """
        # 更新配置中的 plan_list 顺序
        self.config.plan_list = new_data_list
        self.config.save()

        # 重新构建 card_list 的顺序
        new_card_list: list[NotoriousHuntCard] = []
        for data in new_data_list:
            # 找到对应数据的 card
            for card in self.card_list:
                if card.data == data:
                    new_card_list.append(card)
                    break
        self.card_list = new_card_list

        # 更新所有卡片的索引
        for idx, card in enumerate(self.card_list):
            card.update_item(card.data, idx)
