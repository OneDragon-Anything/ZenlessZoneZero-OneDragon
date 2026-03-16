from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, LineEdit

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from zzz_od.application.game_assistant.auto_battle_config import get_auto_battle_op_config_list
from zzz_od.application.game_config_checker.predefined_team_checker import (
    predefined_team_checker_const,
)
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum


class TeamSettingCard(MultiPushSettingCard):

    changed = Signal(PredefinedTeamInfo)

    def __init__(self):
        self.team_info: PredefinedTeamInfo | None = None

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

    def init_setting_card(self, auto_battle_list: list[ConfigItem], team: PredefinedTeamInfo) -> None:
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


class PredefinedTeamInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=predefined_team_checker_const.APP_ID,
            object_name='predefined_team_interface',
            nav_text_cn='预备编队',
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        content = Column()

        self.help_opt = HelpCard(
            title='使用默认队伍名称出现错选时 可更改名字解决',
            content='设置作用于避免选择配队冲突。'
                    '点击开始可根据编队名称自动识别对应的代理人。'
        )
        content.add_widget(self.help_opt)

        self.team_opt_list: list[TeamSettingCard] = []
        team_list = self.ctx.team_config.team_list
        for _ in team_list:
            card = TeamSettingCard()
            card.changed.connect(self._on_team_info_changed)
            self.team_opt_list.append(card)
            content.add_widget(card)

        return content

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)

        auto_battle_list = get_auto_battle_op_config_list('auto_battle')
        team_list = self.ctx.team_config.team_list
        for i in range(len(team_list)):
            if i >= len(self.team_opt_list):
                break
            self.team_opt_list[i].init_setting_card(auto_battle_list, team_list[i])

    def _on_team_info_changed(self, team: PredefinedTeamInfo) -> None:
        self.ctx.team_config.update_team(team)
