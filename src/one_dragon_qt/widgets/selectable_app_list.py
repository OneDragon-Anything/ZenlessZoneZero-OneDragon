"""可选中的应用列表组件

展示一组应用卡片，点击选中某个应用，高亮当前选中项。
支持拖拽排序、添加/移除卡片。
卡片样式与 AppRunCard 一致，使用 MultiPushSettingCard。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget
from qfluentwidgets import (
    FluentIcon,
    TransparentToolButton,
    themeColor,
)

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.draggable_list import DraggableList, DraggableListItem
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)


class SelectableAppCard(DraggableListItem):
    """可选中的应用卡片

    使用 MultiPushSettingCard + DraggableListItem 获得与 AppRunCard 一致的外观和拖拽能力。
    包含：图标 + 标题 + 设置按钮 + 移除按钮。
    选中时图标变为蓝色，未选中时透明度降低。
    """

    clicked = Signal(str)  # app_id
    setting_clicked = Signal(str)  # app_id
    remove_clicked = Signal(str)  # app_id

    def __init__(self, app_id: str, app_name: str, index: int = 0,
                 parent: QWidget | None = None):
        self.app_id = app_id
        self._selected = False

        # 设置按钮
        self.setting_btn = TransparentToolButton(FluentIcon.SETTING, None)
        self.setting_btn.clicked.connect(lambda: self.setting_clicked.emit(self.app_id))

        # 移除按钮
        self.remove_btn = TransparentToolButton(FluentIcon.CLOSE, None)
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.app_id))

        # MultiPushSettingCard 提供标准 Fluent 卡片样式
        content_widget = MultiPushSettingCard(
            btn_list=[self.setting_btn, self.remove_btn],
            icon=FluentIcon.GAME,
            title=gt(app_name),
            parent=parent,
        )

        self._card: MultiPushSettingCard = content_widget

        DraggableListItem.__init__(
            self,
            data=app_id,
            index=index,
            content_widget=content_widget,
            parent=parent,
        )

    @property
    def selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        """设置选中状态"""
        self._selected = selected
        if selected:
            self._card.iconLabel.setIcon(
                FluentIcon.GAME.icon(color=themeColor())
            )
            self._set_opacity(1.0)
        else:
            self._card.iconLabel.setIcon(FluentIcon.GAME)
            self._set_opacity(0.5)

    def _set_opacity(self, opacity: float) -> None:
        """设置卡片透明度"""
        effect = self.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)
        effect.setOpacity(opacity)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.app_id)
        super().mousePressEvent(event)


class SelectableAppList(DraggableList):
    """可选中、可拖拽排序的应用列表

    支持选中、添加、移除、拖拽排序卡片。
    """

    app_selected = Signal(str)  # 选中的 app_id
    app_setting_clicked = Signal(str)  # 设置按钮
    app_removed = Signal(str)  # 移除的 app_id
    app_order_changed = Signal(list)  # 顺序变化后的 app_id 列表

    def __init__(self, parent: QWidget | None = None):
        DraggableList.__init__(self, parent=parent, enable_opacity_effect=True)
        self._cards: list[SelectableAppCard] = []
        self._selected_app_id: str | None = None
        self.order_changed.connect(self._on_order_changed)

    def set_app_list(self, app_list: list[tuple[str, str]]) -> None:
        """设置应用列表

        Args:
            app_list: [(app_id, app_name), ...]
        """
        self._clear_cards()
        seen: set[str] = set()
        for app_id, app_name in app_list:
            if app_id in seen:
                continue
            seen.add(app_id)
            self._add_card(app_id, app_name)

    def add_app(self, app_id: str, app_name: str) -> None:
        """添加一个应用卡片，如果没有选中项则自动选中"""
        for card in self._cards:
            if card.app_id == app_id:
                return
        self._add_card(app_id, app_name)
        if self._selected_app_id is None:
            self.select_app(app_id)
            self.app_selected.emit(app_id)

    def remove_app(self, app_id: str) -> None:
        """移除一个应用卡片"""
        for i, card in enumerate(self._cards):
            if card.app_id == app_id:
                was_selected = card.selected
                card.clicked.disconnect(self._on_card_clicked)
                card.setting_clicked.disconnect(self.app_setting_clicked)
                card.remove_clicked.disconnect(self._on_remove_clicked)
                self._cards.pop(i)
                self.remove_item(i)

                if was_selected:
                    self._selected_app_id = None
                    if self._cards:
                        self.select_app(self._cards[0].app_id)
                    self.app_selected.emit(self._selected_app_id or '')
                break

    def select_app(self, app_id: str) -> None:
        """选中指定应用，未选中的卡片透明度降低"""
        self._selected_app_id = app_id
        for card in self._cards:
            card.set_selected(card.app_id == app_id)

    @property
    def selected_app_id(self) -> str | None:
        return self._selected_app_id

    @property
    def app_ids(self) -> list[str]:
        return [card.app_id for card in self._cards]

    def _add_card(self, app_id: str, app_name: str) -> None:
        idx = len(self._cards)
        card = SelectableAppCard(app_id, app_name, index=idx)
        card.clicked.connect(self._on_card_clicked)
        card.setting_clicked.connect(self.app_setting_clicked)
        card.remove_clicked.connect(self._on_remove_clicked)
        self._cards.append(card)
        self.add_list_item(card)
        card.layout().setContentsMargins(0, 0, 0, 0)
        card.set_selected(False)

    def _clear_cards(self) -> None:
        for card in self._cards:
            card.clicked.disconnect(self._on_card_clicked)
            card.setting_clicked.disconnect(self.app_setting_clicked)
            card.remove_clicked.disconnect(self._on_remove_clicked)
        self._cards.clear()
        self._selected_app_id = None
        self.clear()

    def _on_card_clicked(self, app_id: str) -> None:
        if app_id == self._selected_app_id:
            return
        self.select_app(app_id)
        self.app_selected.emit(app_id)

    def _on_remove_clicked(self, app_id: str) -> None:
        self.remove_app(app_id)
        self.app_removed.emit(app_id)

    def _on_order_changed(self, new_data_list: list) -> None:
        """拖拽排序后重建 _cards 顺序"""
        new_cards: list[SelectableAppCard] = []
        card_map = {card.app_id: card for card in self._cards}
        for app_id in new_data_list:
            if app_id in card_map:
                new_cards.append(card_map[app_id])
        self._cards = new_cards
        self.app_order_changed.emit(self.app_ids)
