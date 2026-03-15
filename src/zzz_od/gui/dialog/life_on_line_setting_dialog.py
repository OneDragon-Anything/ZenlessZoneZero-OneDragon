from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from zzz_od.application.life_on_line import life_on_line_const
from zzz_od.application.life_on_line.life_on_line_config import LifeOnLineConfig
from zzz_od.application.life_on_line.life_on_line_run_record import LifeOnLineRunRecord
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class LifeOnLineSettingDialog(AppSettingDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="拿命验收配置", parent=parent)

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.daily_plan_times_opt = SpinBoxSettingCard(
            icon=FluentIcon.CALENDAR, title='每日次数', maximum=20000, min_width=150
        )
        content_widget.add_widget(self.daily_plan_times_opt)

        self.team_opt = ComboBoxSettingCard(
            icon=FluentIcon.PEOPLE,
            title='预备编队',
        )
        content_widget.add_widget(self.team_opt)

        content_widget.add_stretch(1)

        return content_widget

    def on_dialog_shown(self) -> None:
        super().on_dialog_shown()

        self.config: LifeOnLineConfig = self.ctx.run_context.get_config(
            app_id=life_on_line_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.run_record: LifeOnLineRunRecord = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=life_on_line_const.APP_ID,
        )

        self.daily_plan_times_opt.init_with_adapter(get_prop_adapter(self.config, 'daily_plan_times'))
        self.daily_plan_times_opt.setContent(f'完成次数 当日: {self.run_record.daily_run_times}')

        config_list = ([ConfigItem('游戏内配队', -1)] +
                       [ConfigItem(team.name, team.idx) for team in self.ctx.team_config.team_list])
        self.team_opt.set_options_by_list(config_list)
        self.team_opt.init_with_adapter(get_prop_adapter(self.config, 'predefined_team_idx'))
