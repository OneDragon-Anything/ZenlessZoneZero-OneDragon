from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ExpandSettingCard, FluentIconBase
from qfluentwidgets.components.settings.expand_setting_card import GroupSeparator

from one_dragon.utils.i18_utils import gt


class ExpandSettingCardGroup(ExpandSettingCard):
    """可展开设置卡片组（手风琴式）

    与 SettingCardGroup 有一致的 addSettingCard API。
    """

    def __init__(
        self,
        icon: FluentIconBase | QIcon | str,
        title: str,
        content: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(icon, gt(title), parent=parent)
        if content:
            self.card.setContent(gt(content))
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.viewLayout.setSpacing(0)
        self.setExpand(True)
        self._card_sep_pairs: list[tuple[QWidget, GroupSeparator | None]] = []

    def addHeaderWidget(self, widget: QWidget) -> None:
        """在头部 expandButton 左侧添加操作组件"""
        self.card.addWidget(widget)

    def addSettingCard(self, card: QWidget) -> None:
        """添加设置卡片（自动插入分隔线，去除子卡自身边框）"""
        sep: GroupSeparator | None = None
        if self._card_sep_pairs:
            sep = GroupSeparator(self.view)
            self.viewLayout.addWidget(sep)

        card.paintEvent = lambda _e: None
        card.setParent(self.view)
        self.viewLayout.addWidget(card)
        self._card_sep_pairs.append((card, sep))
        card.installEventFilter(self)
        self._adjustViewSize()

    def addSettingCards(self, cards: list[QWidget]) -> None:
        """批量添加设置卡片"""
        for card in cards:
            self.addSettingCard(card)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Show, QEvent.Type.Hide):
            self._update_separators()
        return super().eventFilter(obj, event)

    def _update_separators(self) -> None:
        """根据卡片可见性更新分隔线：仅当当前卡片可见且前面存在可见卡片时才显示分隔线"""
        has_visible_before = False
        for card, sep in self._card_sep_pairs:
            if sep is not None:
                sep.setVisible(card.isVisible() and has_visible_before)
            if card.isVisible():
                has_visible_before = True
        self._adjustViewSize()
