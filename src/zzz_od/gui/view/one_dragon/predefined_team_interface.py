from PySide6.QtCore import Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    LineEdit,
    MessageBox,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import Margins
from one_dragon_qt.view.app_run_interface import SplitAppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.application.game_config_checker.predefined_team_checker import (
    predefined_team_checker_const,
)
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum


class TeamNameValidator(QValidator):
    """限制编队名称：中文最多 7 个 / 英文最多 14 个（混合按宽度计）"""

    MAX_WIDTH = 14

    def validate(self, input_str: str, pos: int) -> tuple[QValidator.State, str, int]:
        input_width = sum(2 if ord(c) > 127 else 1 for c in input_str)
        if input_width <= self.MAX_WIDTH:
            return QValidator.State.Acceptable, input_str, pos
        return QValidator.State.Invalid, input_str, pos


class TeamSettingCard(SettingCardBase):

    changed = Signal(PredefinedTeamInfo)

    def __init__(self):
        SettingCardBase.__init__(
            self, icon=FluentIcon.PEOPLE, title='',
            margins=Margins(16, 0, 0, 16),
        )
        self.team_info: PredefinedTeamInfo | None = None

        self.titleLabel.hide()
        self.contentLabel.hide()

        # 两行内容布局
        v_layout = QVBoxLayout()
        v_layout.setSpacing(8)
        self.hBoxLayout.addLayout(v_layout)

        # 第一行：编队名称 + 战斗策略
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.name_input = LineEdit()
        self.name_input.setValidator(TeamNameValidator(self.name_input))
        self.name_input.textChanged.connect(self.on_name_changed)
        self.name_input.setFixedWidth(130)
        row1.addWidget(self.name_input)
        row1.addSpacing(13)

        auto_battle_label = CaptionLabel(gt('战斗配置'))
        row1.addWidget(auto_battle_label)

        self.auto_battle_btn = ComboBox()
        self.auto_battle_btn.currentIndexChanged.connect(self.on_auto_battle_changed)
        row1.addWidget(self.auto_battle_btn, stretch=1)
        row1.addSpacing(16)
        v_layout.addLayout(row1)

        # 第二行：三个代理人
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        self.agent_1_btn = EditableComboBox()
        self.agent_1_btn.currentIndexChanged.connect(self.on_agent_1_changed)
        self.agent_1_btn.setFixedWidth(130)
        row2.addWidget(self.agent_1_btn)
        self.agent_2_btn = EditableComboBox()
        self.agent_2_btn.currentIndexChanged.connect(self.on_agent_2_changed)
        self.agent_2_btn.setFixedWidth(130)
        row2.addWidget(self.agent_2_btn)
        self.agent_3_btn = EditableComboBox()
        self.agent_3_btn.currentIndexChanged.connect(self.on_agent_3_changed)
        self.agent_3_btn.setFixedWidth(130)
        row2.addWidget(self.agent_3_btn)
        row2.addSpacing(16)
        v_layout.addLayout(row2)

        self.setFixedHeight(96)

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


class PredefinedTeamInterface(SplitAppRunInterface):

    def __init__(self, ctx: ZContext, parent=None):
        SplitAppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=predefined_team_checker_const.APP_ID,
            object_name='predefined_team_interface',
            nav_text_cn='预备编队',
            parent=parent,
            left_stretch=0,
        )

    def get_widget_at_top(self) -> QWidget:
        top = Column()
        help_card = PushSettingCard(
            icon=FluentIcon.HELP,
            title='预备编队识别',
            text='使用说明',
        )
        help_card.clicked.connect(self._on_help_clicked)
        top.add_widget(help_card)
        return top

    def get_left_widget(self) -> QWidget:
        left_widget = Column(margins=Margins(0, 0, 16, 0))
        self.team_opt_list: list[TeamSettingCard] = []
        team_list = self.ctx.team_config.team_list
        for _ in team_list:
            card = TeamSettingCard()
            card.changed.connect(self._on_team_info_changed)
            self.team_opt_list.append(card)
            left_widget.add_widget(card)
        left_widget.add_stretch(1)
        return left_widget

    def _on_help_clicked(self) -> None:
        content = (
            '▎编队名称\n\n'
            '请确保编队名称与游戏内完全一致，顺序随意，\n'
            '名称不匹配会导致无法识别。\n\n'
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
        SplitAppRunInterface.on_interface_shown(self)

        auto_battle_list = get_auto_battle_op_config_list('auto_battle')
        team_list = self.ctx.team_config.team_list
        for i in range(len(team_list)):
            if i >= len(self.team_opt_list):
                break
            self.team_opt_list[i].init_setting_card(auto_battle_list, team_list[i])

    def _on_team_info_changed(self, team: PredefinedTeamInfo) -> None:
        self.ctx.team_config.update_team(team)
