from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.app_setting.app_setting_flyout import AppSettingFlyout
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import SpinBoxSettingCard
from zzz_od.application.life_on_line import life_on_line_const


class LifeOnLineSettingFlyout(AppSettingFlyout):
    """拿命验收配置弹出框"""

    def _setup_ui(self, layout: QVBoxLayout) -> None:
        self.times_opt = SpinBoxSettingCard(
            icon='', title='每日次数',
            minimum=0, maximum=20000,
            margins=self.card_margins,
        )
        layout.addWidget(self.times_opt)

        self.done_title = SettingCardBase(icon='', title='完成次数', margins=self.card_margins)
        self.done_value = SettingCardBase(icon='', title='', margins=self.card_margins)

        done_row = QHBoxLayout()
        done_row.setSpacing(8)
        done_row.addWidget(self.done_title)
        done_row.addWidget(self.done_value)
        layout.addLayout(done_row)

        self.team_opt = ComboBoxSettingCard(
            icon='', title='预备编队',
            margins=self.card_margins,
        )
        layout.addWidget(self.team_opt)

    def init_config(self) -> None:
        config = self.ctx.run_context.get_config(
            app_id=life_on_line_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        run_record = self.ctx.run_context.get_run_record(
            instance_idx=self.ctx.current_instance_idx,
            app_id=life_on_line_const.APP_ID,
        )

        self.times_opt.init_with_adapter(get_prop_adapter(config, 'daily_plan_times'))
        self.done_value.titleLabel.setText(f'当日: {run_record.daily_run_times}')

        team_list = ([ConfigItem('游戏内配队', -1)] +
                     [ConfigItem(team.name, team.idx) for team in self.ctx.team_config.team_list])
        self.team_opt.set_options_by_list(team_list)
        self.team_opt.init_with_adapter(get_prop_adapter(config, 'predefined_team_idx'))
