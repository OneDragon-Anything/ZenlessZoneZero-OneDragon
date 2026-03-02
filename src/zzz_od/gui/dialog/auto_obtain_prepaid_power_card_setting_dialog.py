from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.editable_combo_box_setting_card import EditableComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.auto_obtain_prepaid_power_card import auto_obtain_prepaid_power_card_const
from zzz_od.application.auto_obtain_prepaid_power_card.auto_obtain_prepaid_power_card_config import (
    AutoObtainPrepaidPowerCardConfig, OutpostLogisticsObtainNumber, MonthlyRestockObtainNumber, FadingSignalObtainNumber,
    UseTheme
)
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class AutoObtainPrepaidPowerCardDialog(AppSettingDialog):
    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="自动合成配置", parent=parent)

        self.auto_obtain_prepaid_power_card_config: AutoObtainPrepaidPowerCardConfig = self.ctx.run_context.get_config(
            app_id=auto_obtain_prepaid_power_card_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.outpost_logistics = SwitchSettingCard(icon=FluentIcon.SHOPPING_CART, title='后勤商店')
        self.outpost_logistics.value_changed.connect(self._on_outpost_logistics_toggled)
        content_widget.add_widget(self.outpost_logistics)

        self.outpost_logistics_obtain_number = EditableComboBoxSettingCard(
            icon=FluentIcon.GAME, title=gt('后勤商店获取数量'),
            options_enum=OutpostLogisticsObtainNumber,
        )
        content_widget.add_widget(self.outpost_logistics_obtain_number)

        self.monthly_restock = SwitchSettingCard(icon=FluentIcon.SHOPPING_CART, title='情报板商店')
        self.monthly_restock.value_changed.connect(self._on_monthly_restock_toggled)
        content_widget.add_widget(self.monthly_restock)

        self.use_theme = ComboBoxSettingCard(icon=FluentIcon.GAME, title='使用主题', options_enum=UseTheme)
        content_widget.add_widget(self.use_theme)

        self.monthly_restock_obtain_number = EditableComboBoxSettingCard(
            icon=FluentIcon.GAME, title=gt('情报板商店获取数量'),
            options_enum=MonthlyRestockObtainNumber,
        )
        content_widget.add_widget(self.monthly_restock_obtain_number)

        self.fading_signal = SwitchSettingCard(icon=FluentIcon.SHOPPING_CART, title='信号残响')
        self.fading_signal.value_changed.connect(self._on_signal_shop_toggled)
        content_widget.add_widget(self.fading_signal)

        self.fading_signal_obtain_number = EditableComboBoxSettingCard(
            icon=FluentIcon.GAME, title=gt('信号残响获取数量'),
            options_enum=FadingSignalObtainNumber,
        )
        content_widget.add_widget(self.fading_signal_obtain_number)

        content_widget.add_stretch(1)

        return content_widget

    def on_dialog_shown(self) -> None:
        super().on_dialog_shown()

        self.outpost_logistics.init_with_adapter(get_prop_adapter(self.auto_obtain_prepaid_power_card_config, 'outpost_logistics'))
        self.outpost_logistics_obtain_number.init_with_adapter(get_prop_adapter(self.auto_obtain_prepaid_power_card_config, 'outpost_logistics_obtain_number'))
        self.monthly_restock.init_with_adapter(get_prop_adapter(self.auto_obtain_prepaid_power_card_config, 'monthly_restock'))
        self.monthly_restock_obtain_number.init_with_adapter(get_prop_adapter(self.auto_obtain_prepaid_power_card_config, 'monthly_restock_obtain_number'))
        self.fading_signal.init_with_adapter(get_prop_adapter(self.auto_obtain_prepaid_power_card_config, "fading_signal"))
        self.fading_signal_obtain_number.init_with_adapter(get_prop_adapter(self.auto_obtain_prepaid_power_card_config, "fading_signal_obtain_number"))

        # 初始化时根据当前配置设置可见性
        self._on_outpost_logistics_toggled(self.auto_obtain_prepaid_power_card_config.outpost_logistics)
        self._on_monthly_restock_toggled(self.auto_obtain_prepaid_power_card_config.monthly_restock)
        self._on_signal_shop_toggled(self.auto_obtain_prepaid_power_card_config.fading_signal)

    def _on_outpost_logistics_toggled(self, checked: bool) -> None:
        # 如果开启后勤商店自动购买储值电卡 显示相关控件 否则隐藏
        self.outpost_logistics_obtain_number.setVisible(checked)

    def _on_monthly_restock_toggled(self, checked: bool) -> None:
        # 如果开启情报板商店自动购买储值电卡 显示相关控件 否则隐藏
        self.monthly_restock_obtain_number.setVisible(checked)
        self.use_theme.setVisible(checked)

    def _on_signal_shop_toggled(self, checked: bool) -> None:
        # 如果开启信号残响自动购买储值电卡 显示相关控件 否则隐藏
        self.fading_signal_obtain_number.setVisible(checked)