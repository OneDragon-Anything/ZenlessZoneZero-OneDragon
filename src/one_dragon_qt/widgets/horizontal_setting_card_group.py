from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout
from typing import List


class HorizontalSettingCardGroup(QWidget):
    """水平布局的设置卡片组，用于在一行中显示多个设置卡片"""

    def __init__(self, cards: List[QWidget] = None, spacing = 2, parent=None):
        super().__init__(parent=parent)

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

    def add_card(self, card: QWidget):
        """添加设置卡片到布局中"""
        card.setParent(self)
        # 确保卡片垂直居中对齐
        self.h_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)

    def add_cards(self, cards: List[QWidget]):
        """批量添加设置卡片"""
        for card in cards:
            self.add_card(card)
