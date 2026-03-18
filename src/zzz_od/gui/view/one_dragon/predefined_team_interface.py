from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    FluentIcon,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    SingleDirectionScrollArea,
    SubtitleLabel,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import Margins
from one_dragon_qt.view.app_run_interface import AppRunInterface, AppRunner
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.log_display_card import LogDisplayCard
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from zzz_od.application.game_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.application.game_config_checker.predefined_team_checker import (
    predefined_team_checker_const,
)
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum


class TeamSettingCard(SettingCardBase):

    changed = Signal(PredefinedTeamInfo)

    def __init__(self):
        SettingCardBase.__init__(self, icon=FluentIcon.PEOPLE, title='')
        self.team_info: PredefinedTeamInfo | None = None

        # 隐藏空的标题和内容标签
        self.titleLabel.hide()
        self.contentLabel.hide()

        self.name_input = LineEdit()
        self.name_input.textChanged.connect(self.on_name_changed)
        self.name_input.setFixedWidth(110)
        self.hBoxLayout.insertWidget(2, self.name_input)
        self.hBoxLayout.insertSpacing(3, 8)

        self.agent_1_btn = EditableComboBox()
        self.agent_1_btn.currentIndexChanged.connect(self.on_agent_1_changed)
        self.agent_1_btn.setFixedWidth(110)
        self.hBoxLayout.insertWidget(4, self.agent_1_btn)
        self.hBoxLayout.insertSpacing(5, 8)

        self.agent_2_btn = EditableComboBox()
        self.agent_2_btn.currentIndexChanged.connect(self.on_agent_2_changed)
        self.agent_2_btn.setFixedWidth(110)
        self.hBoxLayout.insertWidget(6, self.agent_2_btn)
        self.hBoxLayout.insertSpacing(7, 8)

        self.agent_3_btn = EditableComboBox()
        self.agent_3_btn.currentIndexChanged.connect(self.on_agent_3_changed)
        self.agent_3_btn.setFixedWidth(110)
        self.hBoxLayout.insertWidget(8, self.agent_3_btn)
        self.hBoxLayout.insertSpacing(9, 8)

        self.auto_battle_btn = ComboBox()
        self.auto_battle_btn.currentIndexChanged.connect(self.on_auto_battle_changed)
        self.hBoxLayout.insertWidget(10, self.auto_battle_btn)
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

    def get_content_widget(self) -> QWidget:
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 左右结构，占满整个空间
        horizontal_layout = QHBoxLayout()
        horizontal_layout.setSpacing(10)
        horizontal_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(horizontal_layout, stretch=1)

        # 左侧：编队卡片列表（带滚动），占满剩余空间
        horizontal_layout.addLayout(self._get_left_layout(), stretch=1)
        # 右侧：说明卡 + 状态 + 按钮 + 日志，固定宽度
        right_widget = self._get_right_widget()
        horizontal_layout.addWidget(right_widget, stretch=0)

        self.app_runner = AppRunner(self.ctx)
        self.app_runner.state_changed.connect(self.on_context_state_changed)

        return content_widget

    def _get_left_layout(self) -> QVBoxLayout:
        layout = QVBoxLayout()

        scroll_area = SingleDirectionScrollArea()
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        left_widget = Column(margins=Margins(0, 0, 16, 16))
        self.team_opt_list: list[TeamSettingCard] = []
        team_list = self.ctx.team_config.team_list
        for _ in team_list:
            card = TeamSettingCard()
            card.changed.connect(self._on_team_info_changed)
            self.team_opt_list.append(card)
            left_widget.add_widget(card)
        left_widget.add_stretch(1)
        scroll_area.setWidget(left_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        return layout

    def _get_right_widget(self) -> QWidget:
        widget = QWidget()
        widget.setFixedWidth(250)
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        self.help_card = PushSettingCard(
            icon=FluentIcon.HELP,
            title='使用说明',
            text='查看'
        )
        self.help_card.clicked.connect(self._on_help_clicked)
        layout.addWidget(self.help_card)

        layout.addSpacing(4)

        self.state_text = SubtitleLabel()
        self.state_text.setText(f"{gt('当前状态')} {self.ctx.run_context.run_status_text}")
        self.state_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.state_text)

        self.start_btn = PrimaryPushButton(
            text=f"{gt('开始')} {self.ctx.key_start_running.upper()}",
            icon=FluentIcon.PLAY,
        )
        self.start_btn.clicked.connect(self._on_start_clicked)
        layout.addWidget(self.start_btn)

        self.stop_btn = PushButton(
            text=f"{gt('停止')} {self.ctx.key_stop_running.upper()}",
            icon=FluentIcon.CLOSE,
        )
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        layout.addWidget(self.stop_btn)

        self.log_card = LogDisplayCard()
        layout.addWidget(self.log_card, stretch=1)

        return widget

    def _on_help_clicked(self) -> None:
        content = (
            '▎编队名称\n\n'
            '请确保编队名称与游戏内完全一致，\n'
            '名称不匹配会导致选错配队。\n'
            '若出现错选，可尝试修改编队名称。\n\n'
            '不建议使用默认的数字命名编队，\n'
            'OCR 识别数字容易出错，建议使用中文名称。\n\n'
            '▎自动识别\n\n'
            '点击「开始」后将自动打开游戏内预备编队页面，\n'
            '通过截图识别各编队中的代理人并填入左侧配置。'
        )
        w = MessageBox(gt('使用说明'), content, self.window())
        w.cancelButton.hide()
        w.yesButton.setText(gt('确认'))
        w.exec()

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
