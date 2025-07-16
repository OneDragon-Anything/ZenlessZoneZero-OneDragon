from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QCompleter
from qfluentwidgets import FluentIcon, LineEdit
from typing import Optional, List

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.context.zzz_context import ZContext

from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from zzz_od.game_data.agent import AgentEnum


class TeamSettingCard(MultiPushSettingCard):

    changed = Signal(PredefinedTeamInfo)

    def __init__(self):
        self.team_info: Optional[PredefinedTeamInfo] = None

        self.auto_battle_btn = ComboBox()
        self.auto_battle_btn.currentIndexChanged.connect(self.on_auto_battle_changed)

        MultiPushSettingCard.__init__(self, icon=FluentIcon.PEOPLE, title='预备编队',
                                      btn_list=[self.auto_battle_btn])

        self.name_input = LineEdit()
        self.name_input.textChanged.connect(self.on_name_changed)
        self.name_input.setMinimumWidth(65)

        self.agent_1_btn = EditableComboBox()
        self.agent_1_btn.currentIndexChanged.connect(self.on_agent_1_changed)
        self.agent_1_btn.setFixedWidth(110)

        self.agent_2_btn = EditableComboBox()
        self.agent_2_btn.currentIndexChanged.connect(self.on_agent_2_changed)
        self.agent_2_btn.setFixedWidth(110)

        self.agent_3_btn = EditableComboBox()
        self.agent_3_btn.currentIndexChanged.connect(self.on_agent_3_changed)
        self.agent_3_btn.setFixedWidth(110)

        self.hBoxLayout.insertWidget(4, self.agent_1_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.hBoxLayout.insertSpacing(5, 8)
        self.hBoxLayout.insertWidget(6, self.agent_2_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.hBoxLayout.insertSpacing(7, 8)
        self.hBoxLayout.insertWidget(8, self.agent_3_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.hBoxLayout.insertSpacing(9, 8)
        self.hBoxLayout.insertWidget(10, self.name_input, 0, Qt.AlignmentFlag.AlignLeft)
        self.hBoxLayout.insertSpacing(11, 8)

    def init_setting_card(self, auto_battle_list: List[ConfigItem], team: PredefinedTeamInfo) -> None:
        self.team_info = team

        self.name_input.blockSignals(True)
        self.name_input.setText(self.team_info.name)
        self.name_input.blockSignals(False)

        self.auto_battle_btn.set_items(auto_battle_list, team.auto_battle)

        agent_opts = ([ConfigItem(label='代理人', value='unknown')]
            + [ConfigItem(label=i.value.agent_name, value=i.value.agent_id) for i in AgentEnum])

        self.agent_1_btn.set_items(agent_opts, team.agent_id_list[0])
        self.agent_2_btn.set_items(agent_opts, team.agent_id_list[1])
        self.agent_3_btn.set_items(agent_opts, team.agent_id_list[2])

    def on_name_changed(self, value: str) -> None:
        if self.team_info is None:
            return

        self.team_info.name = value
        self.changed.emit(self.team_info)

    def on_auto_battle_changed(self, idx: int) -> None:
        if self.team_info is None:
            return

        self.team_info.auto_battle = self.auto_battle_btn.itemData(idx)
        self.changed.emit(self.team_info)

    def on_agent_1_changed(self, idx: int) -> None:
        if self.team_info is None:
            return

        self.team_info.agent_id_list[0] = self.agent_1_btn.itemData(idx)
        self.changed.emit(self.team_info)

    def on_agent_2_changed(self, idx: int) -> None:
        if self.team_info is None:
            return

        self.team_info.agent_id_list[1] = self.agent_2_btn.itemData(idx)
        self.changed.emit(self.team_info)

    def on_agent_3_changed(self, idx: int) -> None:
        if self.team_info is None:
            return

        self.team_info.agent_id_list[2] = self.agent_3_btn.itemData(idx)
        self.changed.emit(self.team_info)


class SettingTeamInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='setting_team_interface',
            content_widget=None, parent=parent,
            nav_text_cn='预备编队'
        )
        self.ctx: ZContext = ctx

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.help_opt = HelpCard(title='使用默认队伍名称出现错选时 可更改名字解决',
                                 content='本页代理人可在游戏助手中自动识别，设置仅作用于避免式舆防卫战选择配队冲突')
        content_widget.add_widget(self.help_opt)

        self.team_opt_list = []
        team_list = self.ctx.team_config.team_list
        for _ in team_list:
            card = TeamSettingCard()
            card.changed.connect(self.on_team_info_changed)
            self.team_opt_list.append(card)
            content_widget.add_widget(card)

        content_widget.add_stretch(1)

        return content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        auto_battle_list = get_auto_battle_op_config_list('auto_battle')

        team_list = self.ctx.team_config.team_list
        for i in range(len(team_list)):
            if i >= len(self.team_opt_list):
                break

            self.team_opt_list[i].init_setting_card(auto_battle_list, team_list[i])

    def on_team_info_changed(self, team: PredefinedTeamInfo) -> None:
        self.ctx.team_config.update_team(team)