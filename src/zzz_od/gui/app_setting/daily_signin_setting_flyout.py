from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.app_setting.app_setting_flyout import AppSettingFlyout
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from zzz_od.application.daily_signin import daily_signin_const


class DailySignInSettingFlyout(AppSettingFlyout):
    """每日签到配置弹出框"""

    shop_opt: ComboBoxSettingCard

    def _setup_ui(self, layout: QVBoxLayout) -> None:
        self.shop_opt = ComboBoxSettingCard(
            icon='', title='选择签到商店',
            margins=self.card_margins,
        )
        layout.addWidget(self.shop_opt)

    def init_config(self) -> None:
        config = self.ctx.run_context.get_config(
            app_id=daily_signin_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )

        shop_options = [
            ConfigItem('吼吼饼铺', 'hou_hou_bakery'),
            ConfigItem('卦象集录', 'trigrams_collection'),
            ConfigItem('刮刮卡', 'scratch_card')
        ]
        self.shop_opt.set_options_by_list(shop_options)
        self.shop_opt.init_with_adapter(get_prop_adapter(config, 'selected_sign'))
