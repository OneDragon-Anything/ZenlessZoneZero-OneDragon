from __future__ import annotations

from dataclasses import dataclass

from cv2.typing import MatLike
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    FlowLayout,
    FluentIcon,
    PrimaryPushButton,
    SearchLineEdit,
)

from one_dragon.utils.i18_utils import gt
from zzz_od.gui.view.devtools.agent_template_widgets import AgentCard


@dataclass
class AgentTemplateItem:
    """列表中的一个代理人。"""

    agent_id: str
    avatar: MatLike | None
    done_cnt: int
    total_cnt: int


class AgentTemplateList(QWidget):
    """未提交代理人的列表，支持搜索、新建、打开和删除。"""

    new_requested = Signal()
    open_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self._cards: list[AgentCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.toolbar = QWidget()
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)
        toolbar_layout.addWidget(self._new_button())
        toolbar_layout.addStretch(1)
        self.search_edit = SearchLineEdit()
        self.search_edit.setPlaceholderText(gt('搜索代理人'))
        self.search_edit.setFixedWidth(240)
        self.search_edit.textChanged.connect(self._apply_filter)
        toolbar_layout.addWidget(self.search_edit)
        layout.addWidget(self.toolbar)

        self.card_area = QWidget()
        self.card_layout = FlowLayout(self.card_area, needAni=False)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setHorizontalSpacing(12)
        self.card_layout.setVerticalSpacing(12)
        layout.addWidget(self.card_area)

        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(0, 48, 0, 0)
        empty_layout.setSpacing(12)
        empty_layout.addWidget(BodyLabel(gt('没有未提交的代理人')), alignment=Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addWidget(self._new_button(), alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.empty_state)

    def _new_button(self) -> PrimaryPushButton:
        btn = PrimaryPushButton(FluentIcon.ADD, gt('新建'))
        btn.clicked.connect(self.new_requested)
        return btn

    def set_items(self, items: list[AgentTemplateItem]) -> None:
        self.card_layout.takeAllWidgets()  # FlowLayout 的 takeAllWidgets 会同时删除控件
        self._cards = []
        for item in items:
            card = AgentCard(item.agent_id, item.avatar, item.done_cnt, item.total_cnt, parent=self.card_area)
            card.clicked.connect(lambda agent_id=item.agent_id: self.open_requested.emit(agent_id))
            card.delete_requested.connect(self.delete_requested)
            self._cards.append(card)

        has_items = len(self._cards) > 0
        self.toolbar.setVisible(has_items)
        self.empty_state.setVisible(not has_items)
        self._apply_filter(self.search_edit.text())

    def _apply_filter(self, text: str) -> None:
        keyword = text.strip().lower()
        self.card_layout.removeAllWidgets()  # 只移出布局 不删除控件
        for card in self._cards:
            matched = keyword in card.agent_id
            card.setVisible(matched)
            if matched:
                self.card_layout.addWidget(card)
        # FlowLayout 增删控件后不会通知父布局重新计算高度
        self.card_layout.invalidate()
        self.card_area.updateGeometry()
