from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.drive_disc_dismantle import drive_disc_dismantle_const
from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_config import (
    DismantleLevelEnum,
)
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class DriveDiscDismantleSettingDialog(AppSettingDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="驱动盘拆解配置", parent=parent)

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.drive_disc_dismantle_level_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='拆解等级',
                                                                  options_enum=DismantleLevelEnum)
        content_widget.add_widget(self.drive_disc_dismantle_level_opt)

        self.drive_disc_dismantle_abandon_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='全部已弃置')
        content_widget.add_widget(self.drive_disc_dismantle_abandon_opt)
        
        content_widget.add_stretch(1)

        return content_widget

    def on_dialog_shown(self) -> None:
        super().on_dialog_shown()

        self.drive_disc_dismantle_config = self.ctx.run_context.get_config(
            app_id=drive_disc_dismantle_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.drive_disc_dismantle_level_opt.init_with_adapter(get_prop_adapter(self.drive_disc_dismantle_config, 'dismantle_level'))
        self.drive_disc_dismantle_abandon_opt.init_with_adapter(get_prop_adapter(self.drive_disc_dismantle_config, 'dismantle_abandon'))
