from __future__ import annotations

from functools import partial
from typing import List, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    ElevatedCardWidget,
    FluentIcon,
    InfoBadge,
    InfoLevel,
    LineEdit,
    StrongBodyLabel,
    TransparentToolButton,
    isDarkTheme,
    qconfig,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import Margins
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list
from zzz_od.config.team_config import PredefinedTeamInfo
from zzz_od.context.zzz_context import ZContext

from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from zzz_od.gui.widgets.agent_avatar_slot import AgentAvatarSlot


class ClickableWidget(QWidget):

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class TeamNameEditor(QWidget):

    name_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._name: str = ""
        self._editing = False

        self.setObjectName("teamNameEditor")
        self.setMinimumWidth(138)
        self.setFixedHeight(40)

        self.stack_layout = QStackedLayout(self)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)

        self.display_widget = ClickableWidget(self)
        self.display_widget.setObjectName("teamNameDisplay")
        self.display_layout = QHBoxLayout(self.display_widget)
        self.display_layout.setContentsMargins(10, 0, 6, 0)
        self.display_layout.setSpacing(4)

        self.name_label = StrongBodyLabel(self.display_widget)
        self.name_label.setObjectName("teamNameLabel")
        self.display_layout.addWidget(self.name_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self.edit_btn = TransparentToolButton(FluentIcon.EDIT, self.display_widget)
        self.edit_btn.setObjectName("teamNameEditButton")
        self.edit_btn.setFixedSize(24, 24)
        self.display_layout.addWidget(self.edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.editor = LineEdit(self)
        self.editor.setObjectName("teamNameInput")
        self.editor.setFixedHeight(38)
        self.editor.installEventFilter(self)

        self.stack_layout.addWidget(self.display_widget)
        self.stack_layout.addWidget(self.editor)
        self.stack_layout.setCurrentWidget(self.display_widget)

        self.display_widget.clicked.connect(self.start_edit)
        self.edit_btn.clicked.connect(self.start_edit)

    def set_name(self, value: str) -> None:
        normalized_value = value.strip()
        self._name = normalized_value
        self.name_label.setText(normalized_value or gt("编队名称"))
        self.editor.setText(normalized_value)

    def start_edit(self) -> None:
        if self._editing:
            return
        self._editing = True
        self.editor.setText(self._name)
        self.stack_layout.setCurrentWidget(self.editor)
        self.editor.setFocus()
        self.editor.selectAll()

    def commit_edit(self) -> None:
        if not self._editing:
            return

        self._editing = False
        new_name = self.editor.text().strip() or self._name
        changed = new_name != self._name
        self.set_name(new_name)
        self.stack_layout.setCurrentWidget(self.display_widget)
        if changed:
            self.name_changed.emit(new_name)

    def cancel_edit(self) -> None:
        if not self._editing:
            return

        self._editing = False
        self.editor.setText(self._name)
        self.stack_layout.setCurrentWidget(self.display_widget)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.editor and self._editing:
            if event.type() == QEvent.Type.FocusOut:
                self.commit_edit()
            elif event.type() == QEvent.Type.KeyPress:
                key_event = event if isinstance(event, QKeyEvent) else None
                if key_event is not None:
                    if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                        self.commit_edit()
                        return True
                    if key_event.key() == Qt.Key.Key_Escape:
                        self.cancel_edit()
                        return True
        return super().eventFilter(watched, event)


class TeamSettingCard(ElevatedCardWidget):

    changed = Signal(PredefinedTeamInfo)

    def __init__(self):
        super().__init__()
        self.team_info: Optional[PredefinedTeamInfo] = None

        self.setObjectName("teamSettingCard")
        self.setProperty("cardHovered", False)
        self.setMouseTracking(True)
        self.setFixedHeight(110)
        self.setMinimumWidth(392)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 6, 12, 6)
        self.main_layout.setSpacing(4)

        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(10)
        self.main_layout.addLayout(self.header_layout)

        self.name_editor = TeamNameEditor(self)
        self.name_editor.name_changed.connect(self.on_name_changed)
        self.header_layout.addWidget(self.name_editor, 1, Qt.AlignmentFlag.AlignVCenter)

        self.battle_badge = InfoBadge(self, level=InfoLevel.INFOAMTION)
        self.battle_badge.setText(gt("战斗配队"))
        self.header_layout.addWidget(self.battle_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.auto_battle_btn = ComboBox(self)
        self.auto_battle_btn.setObjectName("teamAutoBattleCombo")
        self.auto_battle_btn.setFixedSize(148, 38)
        self.auto_battle_btn.currentIndexChanged.connect(self.on_auto_battle_changed)
        self.header_layout.addWidget(self.auto_battle_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.avatar_layout = QHBoxLayout()
        self.avatar_layout.setContentsMargins(0, 0, 0, 0)
        self.avatar_layout.setSpacing(8)
        self.main_layout.addLayout(self.avatar_layout)

        self.agent_slots: list[AgentAvatarSlot] = []
        for slot_index in range(3):
            slot = AgentAvatarSlot(slot_index + 1, self)
            slot.agent_changed.connect(partial(self.on_agent_changed, slot_index))
            self.agent_slots.append(slot)
            self.avatar_layout.addWidget(slot)
        self.avatar_layout.addStretch(1)

        self._apply_theme_styles()
        qconfig.themeChanged.connect(self._apply_theme_styles)

    def init_setting_card(self, auto_battle_list: List[ConfigItem], team: PredefinedTeamInfo) -> None:
        self.team_info = team

        self.name_editor.blockSignals(True)
        self.name_editor.set_name(self.team_info.name)
        self.name_editor.blockSignals(False)

        self.auto_battle_btn.set_items(auto_battle_list, team.auto_battle)

        for slot_index, slot in enumerate(self.agent_slots):
            agent_id = team.agent_id_list[slot_index] if slot_index < len(team.agent_id_list) else ""
            slot.set_agent_id(agent_id)

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

    def on_agent_changed(self, slot_index: int, agent_id: str) -> None:
        if self.team_info is None:
            return

        while len(self.team_info.agent_id_list) <= slot_index:
            self.team_info.agent_id_list.append("")
        self.team_info.agent_id_list[slot_index] = agent_id
        self.changed.emit(self.team_info)

    def enterEvent(self, event) -> None:
        self.setProperty("cardHovered", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setProperty("cardHovered", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)

    def _apply_theme_styles(self) -> None:
        is_dark = isDarkTheme()
        card_bg = "rgba(34, 38, 45, 234)" if is_dark else "rgba(255, 255, 255, 242)"
        card_border = "rgba(92, 100, 114, 120)" if is_dark else "rgba(191, 198, 210, 160)"
        card_hover_border = "rgba(112, 120, 134, 180)" if is_dark else "rgba(164, 174, 188, 200)"
        editor_bg = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(246, 248, 252, 0.96)"
        editor_hover_bg = "rgba(255, 255, 255, 0.08)" if is_dark else "rgba(241, 244, 249, 1)"
        input_bg = "rgba(29, 32, 39, 0.92)" if is_dark else "rgba(249, 250, 252, 1)"
        border_color = "rgba(92, 100, 114, 180)" if is_dark else "rgba(191, 198, 210, 220)"
        hover_border_color = "rgba(104, 181, 255, 220)" if is_dark else "rgba(82, 142, 248, 220)"
        text_color = "#f5f7fa" if is_dark else "#1f2329"
        secondary_text = "#c5ccd6" if is_dark else "#5f6b7a"
        selected_bg = "rgba(45, 140, 255, 0.20)" if is_dark else "rgba(45, 140, 255, 0.12)"
        hover_bg = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(31, 35, 41, 0.035)"
        badge_bg_light = QColor(54, 119, 255, 24)
        badge_bg_dark = QColor(54, 119, 255, 88)

        combo_style = f"""
        ComboBox#teamAutoBattleCombo {{
            background-color: {input_bg};
            border: 1px solid {border_color};
            border-radius: 6px;
            color: {text_color};
            padding: 0 10px;
            min-height: 38px;
        }}
        ComboBox#teamAutoBattleCombo:hover {{
            border-color: {hover_border_color};
        }}
        ComboBox#teamAutoBattleCombo:focus {{
            border-color: {hover_border_color};
        }}
        ComboBox#teamAutoBattleCombo QAbstractItemView {{
            background-color: {input_bg};
            border: 1px solid {border_color};
            color: {text_color};
            outline: none;
            padding: 6px;
            selection-background-color: {selected_bg};
        }}
        ComboBox#teamAutoBattleCombo QAbstractItemView::item {{
            min-height: 38px;
            padding: 0 10px;
            margin: 2px 0;
            border-radius: 6px;
        }}
        ComboBox#teamAutoBattleCombo QAbstractItemView::item:hover {{
            background: {hover_bg};
        }}
        ComboBox#teamAutoBattleCombo QAbstractItemView::item:selected {{
            background: {selected_bg};
            color: {text_color};
        }}
        """

        self.setStyleSheet(
            f"""
            ElevatedCardWidget#teamSettingCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 12px;
            }}
            ElevatedCardWidget#teamSettingCard[cardHovered="true"] {{
                border: 1px solid {card_hover_border};
            }}
            QWidget#teamNameDisplay {{
                background-color: {editor_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            QWidget#teamNameDisplay:hover {{
                background-color: {editor_hover_bg};
                border: 1px solid {hover_border_color};
            }}
            StrongBodyLabel#teamNameLabel {{
                color: {text_color};
                padding-left: 1px;
            }}
            TransparentToolButton#teamNameEditButton {{
                border: none;
                background: transparent;
                color: {secondary_text};
            }}
            TransparentToolButton#teamNameEditButton:hover {{
                background: {hover_bg};
                border-radius: 6px;
                color: {text_color};
            }}
            LineEdit#teamNameInput {{
                background-color: {input_bg};
                border: 1px solid {hover_border_color};
                border-radius: 6px;
                color: {text_color};
                padding: 0 10px;
                min-height: 38px;
            }}
            """
        )
        self.auto_battle_btn.setStyleSheet(combo_style)
        self.battle_badge.setCustomBackgroundColor(badge_bg_light, badge_bg_dark)
        self.battle_badge.setStyleSheet(
            f"""
            color: {('#dbe8ff' if is_dark else '#2f6fed')};
            padding: 2px 8px;
            """
        )


class SettingTeamInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='setting_team_interface',
            content_widget=None, parent=parent,
            nav_text_cn='预备编队'
        )

    def get_content_widget(self) -> QWidget:
        zero_margins = Margins(0, 0, 0, 0)
        content_widget = Column(spacing=8, margins=zero_margins)

        self.help_opt = HelpCard(title='使用默认队伍名称出现错选时 可更改名字解决',
                                 content='本页代理人可在游戏助手中自动识别，设置仅作用于避免式舆防卫战选择配队冲突')
        content_widget.add_widget(self.help_opt)

        self.team_opt_list = []
        team_list = self.ctx.team_config.team_list
        for row_start in range(0, len(team_list), 2):
            row = Row(spacing=10, margins=zero_margins)
            row_card_count = 0
            for _ in range(row_start, min(row_start + 2, len(team_list))):
                card = TeamSettingCard()
                card.changed.connect(self.on_team_info_changed)
                self.team_opt_list.append(card)
                row.h_layout.addWidget(card, 1)
                row_card_count += 1
            if row_card_count < 2:
                row.add_stretch(1)
            content_widget.add_widget(row)

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
