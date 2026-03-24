from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.app_setting.app_setting_flyout import AppSettingFlyout
from one_dragon_qt.widgets.setting_card.editable_combo_box_setting_card import (
    EditableComboBoxSettingCard,
)
from zzz_od.application.random_play.random_play_config import (
    RANDOM_AGENT_NAME,
)
from zzz_od.game_data.agent import AgentEnum


class RandomPlaySettingFlyout(AppSettingFlyout):
    """录像店配置弹出框"""

    def _setup_ui(self, layout: QVBoxLayout) -> None:
        agents_list = [ConfigItem(RANDOM_AGENT_NAME)] + [
            ConfigItem(agent_enum.value.agent_name)
            for agent_enum in AgentEnum
        ]

        self.random_play_agent_1 = EditableComboBoxSettingCard(
            icon='', title='影像店代理人-1',
            options_list=agents_list,
            margins=self.card_margins,
        )
        layout.addWidget(self.random_play_agent_1)

        self.random_play_agent_2 = EditableComboBoxSettingCard(
            icon='', title='影像店代理人-2',
            options_list=agents_list,
            margins=self.card_margins,
        )
        layout.addWidget(self.random_play_agent_2)

    def init_config(self) -> None:
        config = self.ctx.run_context.get_config(
            app_id='random_play',
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.random_play_agent_1.init_with_adapter(get_prop_adapter(config, 'agent_name_1'))
        self.random_play_agent_2.init_with_adapter(get_prop_adapter(config, 'agent_name_2'))
