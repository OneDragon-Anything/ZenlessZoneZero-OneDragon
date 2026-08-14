from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.app_setting.app_setting_flyout import AppSettingFlyout
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.coffee import coffee_app_const
from zzz_od.application.coffee.coffee_config import (
    CoffeeChooseWay,
    CoffeeTransportPoint,
)


class CoffeeSettingFlyout(AppSettingFlyout):
    """咖啡店配置弹出框"""

    def _setup_ui(self, layout: QVBoxLayout) -> None:
        self.transport_point_opt = ComboBoxSettingCard(
            icon='',
            title='传送地点',
            content='选择前往的咖啡店',
            options_enum=CoffeeTransportPoint,
            margins=self.card_margins,
        )
        layout.addWidget(self.transport_point_opt)

        self.choose_way_opt = ComboBoxSettingCard(
            icon='',
            title='咖啡选择',
            content=CoffeeChooseWay.TINMAN_ONLY.value.desc,
            options_enum=CoffeeChooseWay,
            margins=self.card_margins,
        )
        layout.addWidget(self.choose_way_opt)

        self.run_charge_plan_afterwards_opt = SwitchSettingCard(
            icon='',
            title='结束后运行体力计划',
            content='咖啡店在体力计划后运行可开启',
            margins=self.card_margins,
        )
        layout.addWidget(self.run_charge_plan_afterwards_opt)

    def init_config(self) -> None:
        config = self.ctx.run_context.get_config(
            app_id=coffee_app_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.transport_point_opt.init_with_adapter(get_prop_adapter(config, 'transport_point'))
        self.choose_way_opt.init_with_adapter(get_prop_adapter(config, 'choose_way'))
        self.run_charge_plan_afterwards_opt.init_with_adapter(
            get_prop_adapter(config, 'run_charge_plan_afterwards')
        )
