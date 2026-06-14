from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget


class HorizontalSettingCardGroup(QWidget):
    """水平布局的设置卡片组，用于在一行中显示多个设置卡片"""

    def __init__(
        self,
        cards: list[QWidget] | None = None,
        spacing: int = 2,
        parent: QWidget | None = None,
        equal_width: bool = False,
    ) -> None:
        super().__init__(parent=parent)
        self.equal_width: bool = equal_width

        # 创建水平布局
        self.h_layout = QHBoxLayout(self)
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.h_layout.setSpacing(spacing)
        self.h_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 设置固定高度，确保与设置卡片高度一致
        self.setFixedHeight(50)

        # 添加卡片
        if cards:
            for card in cards:
                self.add_card(card)

    def add_card(self, card: QWidget) -> None:
        """添加设置卡片到布局中"""
        card.setParent(self)
        if self.equal_width:
            card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        # 确保卡片垂直居中对齐
        self.h_layout.addWidget(card, 1, Qt.AlignmentFlag.AlignTop)

    def add_cards(self, cards: list[QWidget]) -> None:
        """批量添加设置卡片"""
        for card in cards:
            self.add_card(card)
