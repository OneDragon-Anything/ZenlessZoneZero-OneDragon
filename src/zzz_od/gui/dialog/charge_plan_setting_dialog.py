from __future__ import annotations

from typing import TYPE_CHECKING, List

from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    FluentIcon,
    PrimaryPushButton,
    PushButton, Dialog,
)

from one_dragon.base.operation.application import application_const
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.draggable_list import DraggableList
from one_dragon_qt.widgets.horizontal_setting_card_group import (
    HorizontalSettingCardGroup,
)
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.charge_plan import charge_plan_const
from zzz_od.application.charge_plan.charge_plan_config import (
    ChargePlanItem,
    RestoreChargeEnum,
)
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog
from zzz_od.gui.view.one_dragon.charge_plan_interface import ChargePlanCard

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class ChargePlanSettingDialog(AppSettingDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="体力计划配置", parent=parent)

    def get_content_widget(self) -> QWidget:
        self.content_widget = Column()

        self.loop_opt = SwitchSettingCard(icon=FluentIcon.SYNC, title='循环执行', content='开启时 会循环执行到体力用尽')
        self.skip_plan_opt = SwitchSettingCard(icon=FluentIcon.FLAG, title='跳过计划', content='开启时 自动跳过体力不足的计划')
        self.content_widget.add_widget(HorizontalSettingCardGroup([self.loop_opt, self.skip_plan_opt], spacing=6))

        # 2.5版本已移除家政券功能，暂时关闭UI
        # self.coupon_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='使用家政券', content='运行区域巡防时使用家政券')
        self.restore_charge_opt = ComboBoxSettingCard(icon=FluentIcon.ADD_TO, title='恢复电量', options_enum=RestoreChargeEnum)
        # self.content_widget.add_widget(HorizontalSettingCardGroup([self.coupon_opt, self.restore_charge_opt], spacing=6))
        self.content_widget.add_widget(self.restore_charge_opt)

        self.cancel_btn = PushButton(icon=FluentIcon.CANCEL, text=gt('撤销'))
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)

        self.remove_all_completed_btn = PushButton(
            icon=FluentIcon.DELETE, text='删除已完成'
        )
        self.remove_all_completed_btn.clicked.connect(self._on_remove_all_completed_clicked)

        self.remove_all_btn = PushButton(
            icon=FluentIcon.DELETE, text='删除所有'
        )
        self.remove_all_btn.clicked.connect(self._on_remove_all_clicked)

        self.remove_setting_card = MultiPushSettingCard(btn_list=[
            self.cancel_btn,
            self.remove_all_completed_btn,
            self.remove_all_btn
        ], icon=FluentIcon.DELETE, title='删除体力计划')
        self.content_widget.add_widget(self.remove_setting_card)

        # 创建可拖动的列表容器
        self.drag_list = DraggableList()
        self.drag_list.order_changed.connect(self._on_order_changed)
        self.content_widget.add_widget(self.drag_list)

        self.card_list: List[ChargePlanCard] = []

        self.plus_btn = PrimaryPushButton(text=gt('新增'))
        self.plus_btn.clicked.connect(self._on_add_clicked)
        self.content_widget.add_widget(self.plus_btn, stretch=1)

        return self.content_widget

    def on_dialog_shown(self) -> None:
        super().on_dialog_shown()

        self.config = self.ctx.run_context.get_config(
            app_id=charge_plan_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.update_plan_list_display()

        self.loop_opt.init_with_adapter(get_prop_adapter(self.config, 'loop'))
        self.skip_plan_opt.init_with_adapter(get_prop_adapter(self.config, 'skip_plan'))
        # self.coupon_opt.init_with_adapter(get_prop_adapter(self.config, 'use_coupon'))  # 2.4版本已移除家政券功能
        self.restore_charge_opt.init_with_adapter(get_prop_adapter(self.config, 'restore_charge'))

    def update_plan_list_display(self):
        plan_list = self.config.plan_list

        if len(plan_list) > len(self.card_list):
            self.content_widget.remove_widget(self.plus_btn)

            while len(self.card_list) < len(plan_list):
                idx = len(self.card_list)
                card = ChargePlanCard(self.ctx, idx, self.config.plan_list[idx],
                                      config=self.config)
                card.changed.connect(self._on_plan_item_changed)
                card.delete.connect(self._on_plan_item_deleted)
                card.move_top.connect(self._on_plan_item_move_top)

                self.card_list.append(card)
                # 使用 DraggableList 的 add_list_item 方法添加 ChargePlanCard
                self.drag_list.add_list_item(card)

            self.content_widget.add_widget(self.plus_btn, stretch=1)

        for idx, plan in enumerate(plan_list):
            self.card_list[idx].update_item(plan, idx)

        while len(self.card_list) > len(plan_list):
            self.drag_list.remove_item(len(self.card_list) - 1)
            self.card_list.pop(-1)

    def _on_add_clicked(self) -> None:
        from zzz_od.gui.view.one_dragon.charge_plan_dialog import ChargePlanDialog
        dialog = ChargePlanDialog(self.ctx, self.config, parent=self)
        result = dialog.exec()
        if result:
            self.config.add_plan(dialog.plan)
        self.update_plan_list_display()

    def _on_plan_item_changed(self, idx: int, plan: ChargePlanItem) -> None:
        self.config.update_plan(idx, plan)

    def _on_plan_item_deleted(self, idx: int) -> None:
        self.config.delete_plan(idx)
        self.update_plan_list_display()

    def _on_plan_item_move_top(self, idx: int) -> None:
        self.config.move_top(idx)
        self.update_plan_list_display()

    def _on_remove_all_completed_clicked(self) -> None:
        dialog = Dialog('警告', '是否删除所有已完成的体力计划？', self)
        dialog.setTitleBarVisible(False)
        dialog.yesButton.setText('确定')
        dialog.cancelButton.setText('取消')
        if dialog.exec():
            self.plan_list_backup = self.config.plan_list.copy()
            not_completed_plans = [plan for plan in self.config.plan_list
                                   if plan.run_times < plan.plan_times]
            self.config.plan_list = not_completed_plans.copy()
            self.config.save()
            self.cancel_btn.setEnabled(True)
        self.update_plan_list_display()

    def _on_remove_all_clicked(self) -> None:
        dialog = Dialog('警告', '是否删除所有体力计划？', self)
        dialog.setTitleBarVisible(False)
        dialog.yesButton.setText('确定')
        dialog.cancelButton.setText('取消')
        if dialog.exec():
            self.plan_list_backup = self.config.plan_list.copy()
            self.config.plan_list.clear()
            self.config.save()
            self.cancel_btn.setEnabled(True)
        self.update_plan_list_display()

    def _on_cancel_clicked(self) -> None:
        self.config.plan_list = self.plan_list_backup.copy()
        self.cancel_btn.setEnabled(False)
        self.update_plan_list_display()

    def _on_order_changed(self, new_data_list: list) -> None:
        """
        拖拽改变顺序后的回调

        Args:
            new_data_list: 新顺序的数据列表
        """
        # 更新配置中的 plan_list 顺序
        self.config.plan_list = new_data_list
        self.config.save()

        # 重新构建 card_list 的顺序
        new_card_list: List[ChargePlanCard] = []
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
