from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.app_setting.app_setting_flyout import AppSettingFlyout
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.drive_disc_dismantle import drive_disc_dismantle_const
from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_config import (
    DismantleLevelEnum,
)


class DriveDiscDismantleSettingFlyout(AppSettingFlyout):
    """驱动盘拆解配置弹出框"""

    def _setup_ui(self, layout: QVBoxLayout) -> None:
        self.level_opt = ComboBoxSettingCard(
            icon='', title='拆解等级',
            options_enum=DismantleLevelEnum,
            margins=self.card_margins,
        )
        layout.addWidget(self.level_opt)

        self.abandon_switch = SwitchSettingCard(
            icon='', title='全部已弃置',
            margins=self.card_margins,
        )
        layout.addWidget(self.abandon_switch)

    def init_config(self) -> None:
        config = self.ctx.run_context.get_config(
            app_id=drive_disc_dismantle_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.level_opt.init_with_adapter(get_prop_adapter(config, 'dismantle_level'))
        self.abandon_switch.init_with_adapter(get_prop_adapter(config, 'dismantle_abandon'))
