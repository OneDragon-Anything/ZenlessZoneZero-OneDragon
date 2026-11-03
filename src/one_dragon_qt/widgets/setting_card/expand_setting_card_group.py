from typing import Any

from PySide6.QtCore import QAbstractAnimation, QEvent, QObject, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ExpandSettingCard, FluentIcon
from qfluentwidgets.components.settings.expand_setting_card import GroupSeparator
from shiboken6 import isValid

from one_dragon.utils.i18_utils import gt


class ExpandSettingCardGroup(ExpandSettingCard):
    """可展开设置卡片组（手风琴式）

    与 SettingCardGroup 有一致的 addSettingCard API。
    """

    def __init__(
        self,
        icon: str | QIcon | FluentIcon,
        title: str,
        content: str | None = None,
        initial_expand: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(icon, gt(title), parent=parent)
        if content:
            self.card.setContent(gt(content))
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.viewLayout.setSpacing(0)
        self._card_sep_pairs: list[tuple[QWidget, GroupSeparator | None]] = []
        if initial_expand:
            self.setExpand(True)
        self.expandAni.valueChanged.connect(self._sync_parent_layout)
        self.expandAni.finished.connect(self._refresh_view_size)

    def addHeaderWidget(self, widget: QWidget) -> None:
        """在头部 expandButton 左侧添加操作组件"""
        self.card.addWidget(widget)

    def addSettingCard(self, card: QWidget) -> None:
        """添加设置卡片（自动插入分隔线，去除子卡自身边框）"""
        sep: GroupSeparator | None = None
        if self._card_sep_pairs:
            sep = GroupSeparator(self.view)
            self.viewLayout.addWidget(sep)

        def paint_event_override(_e) -> None:
            return None

        paint_event_override_any: Any = paint_event_override
        card.paintEvent = paint_event_override_any
        card.setParent(self.view)
        self.viewLayout.addWidget(card)
        self._card_sep_pairs.append((card, sep))
        card.installEventFilter(self)
        self._adjustViewSize()

    def addSettingCards(self, cards: list[QWidget]) -> None:
        """批量添加设置卡片"""
        for card in cards:
            self.addSettingCard(card)

    def eventFilter(self, arg__1: QObject, arg__2: QEvent) -> bool:
        if arg__2.type() in (QEvent.Type.Show, QEvent.Type.Hide):
            QTimer.singleShot(0, self._update_separators)
        elif arg__2.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest):
            if self.expandAni.state() == QAbstractAnimation.State.Running:
                return super().eventFilter(arg__1, arg__2)
            QTimer.singleShot(0, self._refresh_view_size)
        return super().eventFilter(arg__1, arg__2)

    def _update_separators(self) -> None:
        """根据卡片可见性更新分隔线：仅当当前卡片可见且前面存在可见卡片时才显示分隔线"""
        if not isValid(self):
            return
        has_visible_before = False
        for card, sep in self._card_sep_pairs:
            if not isValid(card):
                continue
            if sep is not None:
                sep.setVisible(card.isVisible() and has_visible_before)
            if card.isVisible():
                has_visible_before = True
        self._refresh_view_size()

    def _refresh_view_size(self) -> None:
        """同步重算展开区域尺寸，确保子卡高度变化能传递到手风琴容器。"""
        self._adjustViewSize()
        self._sync_parent_layout()

    def _sync_parent_layout(self, *_args) -> None:
        """在动画帧内同步父布局，避免手风琴底部与后续卡片之间出现瞬时 gap/重叠。"""
        self.updateGeometry()

        parent = self.parentWidget()
        while parent is not None:
            parent.updateGeometry()
            layout = parent.layout()
            if layout is not None:
                layout.activate()
            parent = parent.parentWidget()
