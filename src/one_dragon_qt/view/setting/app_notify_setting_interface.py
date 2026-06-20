from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget
from qfluentwidgets import (
    FluentIcon,
    SettingCardGroup,
)

from one_dragon.base.config.notify_config import NotifyDetailMode, NotifyLifecycleMode
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.horizontal_setting_card_group import (
    HorizontalSettingCardGroup,
)
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface


class AppNotifySettingCard(SettingCardBase):
    """单个应用的通知设置卡片。"""

    def __init__(self, ctx: OneDragonContext, app_id: str, app_name: str, parent: QWidget | None = None) -> None:
        self.ctx: OneDragonContext = ctx
        self.app_id: str = app_id

        SettingCardBase.__init__(
            self,
            icon='',
            title=app_name,
            parent=parent,
        )

        self.lifecycle_combo = ComboBox(self)
        self.detail_combo = ComboBox(self)
        self._init_options()

        lifecycle_label = QLabel(gt('应用'), self)
        detail_label = QLabel(gt('节点'), self)
        self.hBoxLayout.addWidget(lifecycle_label, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.lifecycle_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.hBoxLayout.addWidget(detail_label, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.detail_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.lifecycle_combo.currentIndexChanged.connect(self._on_lifecycle_changed)
        self.detail_combo.currentIndexChanged.connect(self._on_detail_changed)
        self.reload_from_config()

    def _init_options(self) -> None:
        """初始化下拉框选项。"""
        self.lifecycle_combo.set_items([item.value for item in NotifyLifecycleMode])
        self.detail_combo.set_items([item.value for item in NotifyDetailMode])

        self.lifecycle_combo.setFixedWidth(120)
        self.detail_combo.setFixedWidth(90)

    def reload_from_config(self) -> None:
        """从配置刷新显示值。"""
        self.lifecycle_combo.setValue(
            self.ctx.notify_config.get_app_lifecycle_mode(self.app_id),
            emit_signal=False,
        )
        self.detail_combo.setValue(
            self.ctx.notify_config.get_app_detail_mode(self.app_id),
            emit_signal=False,
        )

    def _on_lifecycle_changed(self, index: int) -> None:
        """应用通知模式变更。"""
        self.ctx.notify_config.set_app_lifecycle_mode(self.app_id, self.lifecycle_combo.getValue())

    def _on_detail_changed(self, index: int) -> None:
        """节点通知模式变更。"""
        self.ctx.notify_config.set_app_detail_mode(self.app_id, self.detail_combo.getValue())


class NotifySettingInterface(VerticalScrollInterface):
    """推入式通知设置界面。"""

    def __init__(self, ctx: OneDragonContext, parent: QWidget | None = None) -> None:
        self.ctx: OneDragonContext = ctx
        self.merge_error_notify_switch: SwitchSettingCard | None = None
        self.app_cards: dict[str, AppNotifySettingCard] = {}

        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='notify_setting_interface',
            nav_text_cn='通知设置',
            nav_icon=FluentIcon.MESSAGE,
            parent=parent,
        )

    def get_content_widget(self) -> QWidget:
        """创建通知设置内容。"""
        content_widget = Column()

        basic_group = SettingCardGroup(gt('通用'))
        content_widget.add_widget(basic_group)

        self.merge_error_notify_switch = SwitchSettingCard(
            icon=FluentIcon.INFO,
            title='合并模式失败节点立即通知',
            content='节点通知为全部合并时，失败节点会额外立即推送',
            on_text_cn='开启',
            off_text_cn='关闭',
        )
        self.merge_error_notify_switch.value_changed.connect(self._on_merge_error_notify_changed)
        basic_group.addSettingCard(self.merge_error_notify_switch)

        app_group = SettingCardGroup(gt('应用通知'))
        content_widget.add_widget(app_group)

        row_cards: list[AppNotifySettingCard] = []
        for app_id, app_name in self.ctx.notify_config.app_map.items():
            card = AppNotifySettingCard(self.ctx, app_id, app_name)
            self.app_cards[app_id] = card
            row_cards.append(card)
            if len(row_cards) == 2:
                app_group.addSettingCard(HorizontalSettingCardGroup(row_cards, spacing=6))
                row_cards = []

        if row_cards:
            placeholder = QWidget()
            placeholder.setFixedHeight(50)
            placeholder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            app_group.addSettingCard(HorizontalSettingCardGroup([*row_cards, placeholder], spacing=6))

        content_widget.add_stretch(1)
        return content_widget

    def on_interface_shown(self) -> None:
        """界面显示时刷新配置值。"""
        VerticalScrollInterface.on_interface_shown(self)
        if self.merge_error_notify_switch is not None:
            self.merge_error_notify_switch.setValue(
                self.ctx.notify_config.merge_error_immediate_notify,
                emit_signal=False,
            )
        for card in self.app_cards.values():
            card.reload_from_config()

    def _on_merge_error_notify_changed(self, value: bool) -> None:
        """合并模式失败节点立即通知开关变更。"""
        self.ctx.notify_config.merge_error_immediate_notify = value
