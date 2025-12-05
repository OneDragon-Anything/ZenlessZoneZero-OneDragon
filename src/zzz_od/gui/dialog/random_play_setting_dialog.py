from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.editable_combo_box_setting_card import (
    EditableComboBoxSettingCard,
)
from zzz_od.application.random_play.random_play_config import (
    RANDOM_AGENT_NAME,
)
from zzz_od.game_data.agent import AgentEnum
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class RandomPlaySettingDialog(AppSettingDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="录像店配置", parent=parent)

    def get_content_widget(self) -> QWidget:
        content_widget = Column()
        agents_list = [ConfigItem(RANDOM_AGENT_NAME)] + [
                ConfigItem(agent_enum.value.agent_name)
                for agent_enum in AgentEnum
            ]
        self.random_play_agent_1 = EditableComboBoxSettingCard(
            icon=FluentIcon.PEOPLE, title=gt('影像店代理人-1'),
            options_list=agents_list,
        )
        self.random_play_agent_1.combo_box.setFixedWidth(110)
        content_widget.add_widget(self.random_play_agent_1)

        self.random_play_agent_2 = EditableComboBoxSettingCard(
            icon=FluentIcon.PEOPLE, title=gt('影像店代理人-2'),
            options_list=agents_list,
        )
        self.random_play_agent_2.combo_box.setFixedWidth(110)
        content_widget.add_widget(self.random_play_agent_2)
        
        content_widget.add_stretch(1)

        return content_widget

    def on_dialog_shown(self) -> None:
        super().on_dialog_shown()

        self.random_play_config = self.ctx.run_context.get_config(
            app_id='random_play',
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.random_play_agent_1.init_with_adapter(get_prop_adapter(self.random_play_config, 'agent_name_1'))
        self.random_play_agent_2.init_with_adapter(get_prop_adapter(self.random_play_config, 'agent_name_2'))
