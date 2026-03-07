from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.auto_synthetic import auto_synthetic_const
from zzz_od.application.auto_synthetic.auto_synthetic_config import SourceEtherBatteryAutoSyntheticQuantity, \
    AutoSyntheticConfig
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class AutoSyntheticSettingDialog(AppSettingDialog):
    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="自动合成配置", parent=parent)

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.auto_synthetic_hifi_master_copy = SwitchSettingCard(icon=FluentIcon.GAME, title='高保真母盘')
        content_widget.add_widget(self.auto_synthetic_hifi_master_copy)

        self.auto_synthetic_source_ether_battery = SwitchSettingCard(icon=FluentIcon.GAME, title='以太电池')
        self.auto_synthetic_source_ether_battery.value_changed.connect(self._on_auto_synthetic_source_ether_battery_toggled)
        content_widget.add_widget(self.auto_synthetic_source_ether_battery)

        self.source_ether_battery_auto_synthetic_quantity = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='以太电池自动合成数量', options_enum=SourceEtherBatteryAutoSyntheticQuantity
        )
        content_widget.add_widget(self.source_ether_battery_auto_synthetic_quantity)

        content_widget.add_stretch(1)

        return content_widget

    def on_dialog_shown(self) -> None:
        super().on_dialog_shown()

        self.auto_synthetic_config: AutoSyntheticConfig = self.ctx.run_context.get_config(
            app_id=auto_synthetic_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.auto_synthetic_hifi_master_copy.init_with_adapter(get_prop_adapter(self.auto_synthetic_config, 'hifi_master_copy'))
        self.auto_synthetic_source_ether_battery.init_with_adapter(get_prop_adapter(self.auto_synthetic_config, 'source_ether_battery'))
        self.source_ether_battery_auto_synthetic_quantity.init_with_adapter(get_prop_adapter(self.auto_synthetic_config, 'source_ether_battery_auto_synthetic_quantity'))

        # 初始化时根据当前配置设置可见性
        self._on_auto_synthetic_source_ether_battery_toggled(self.auto_synthetic_config.source_ether_battery)

    def _on_auto_synthetic_source_ether_battery_toggled(self, checked: bool) -> None:
        # 如果开启以太电池自动合成 显示相关控件 否则隐藏
        visible = checked
        self.source_ether_battery_auto_synthetic_quantity.setVisible(visible)