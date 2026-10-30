from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout
from qfluentwidgets import PushButton

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.app_setting.app_setting_flyout import AppSettingFlyout
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.application.intel_board import intel_board_const
from zzz_od.application.intel_board.intel_board_run_record import IntelBoardRunRecord


class IntelBoardSettingFlyout(AppSettingFlyout):
    """情报板配置弹出框"""

    def _setup_ui(self, layout: QVBoxLayout) -> None:
        self.predefined_team_opt = ComboBoxSettingCard(
            icon='', title='预备编队',
            margins=self.card_margins,
        )
        self.predefined_team_opt.value_changed.connect(self._on_team_changed)
        layout.addWidget(self.predefined_team_opt)

        self.auto_battle_opt = ComboBoxSettingCard(
            icon='', title='自动战斗',
            margins=self.card_margins,
        )
        layout.addWidget(self.auto_battle_opt)

        self.exp_grind_switch = SwitchSettingCard(
            icon='', title='刷满经验',
            margins=self.card_margins,
        )
        layout.addWidget(self.exp_grind_switch)

        self.reset_btn = PushButton(gt('重置进度'))
        self.reset_btn.clicked.connect(self._on_reset_progress)
        layout.addWidget(self.reset_btn)

    def init_config(self) -> None:
        self.config = self.ctx.run_context.get_config(
            app_id=intel_board_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )

        team_list = ([ConfigItem('游戏内配队', -1)] +
                     [ConfigItem(team.name, team.idx) for team in self.ctx.team_config.team_list])
        self.predefined_team_opt.set_options_by_list(team_list)
        self.predefined_team_opt.init_with_adapter(get_prop_adapter(self.config, 'predefined_team_idx'))

        auto_battle_list = get_auto_battle_op_config_list(sub_dir='auto_battle')
        self.auto_battle_opt.set_options_by_list(auto_battle_list)
        self.auto_battle_opt.init_with_adapter(get_prop_adapter(self.config, 'auto_battle_config'))

        self.exp_grind_switch.init_with_adapter(get_prop_adapter(self.config, 'exp_grind_mode'))

        self._update_auto_battle_visibility()

    def _on_team_changed(self, idx: int, value: object) -> None:
        self._update_auto_battle_visibility()

    def _update_auto_battle_visibility(self) -> None:
        visible = self.config and self.config.predefined_team_idx == -1
        self.auto_battle_opt.setVisible(visible)

    def _on_reset_progress(self) -> None:
        """重置情报板进度完成标记"""
        run_record: IntelBoardRunRecord = self.ctx.run_context.get_run_record(
            app_id=intel_board_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
        )
        run_record.progress_complete = False
        run_record.notorious_hunt_count = 0
        run_record.expert_challenge_count = 0
        run_record.base_exp = 0
        self.reset_btn.setText(gt('已重置'))
        self.reset_btn.setEnabled(False)
