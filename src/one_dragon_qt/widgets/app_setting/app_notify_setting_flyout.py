from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (
    FlyoutViewBase,
    SettingCard,
    SubtitleLabel,
    TeachingTipTailPosition,
)

from one_dragon.base.config.notify_config import NotifyDetailMode, NotifyLifecycleMode
from one_dragon.base.operation.one_dragon_context import OneDragonContext
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import Margins
from one_dragon_qt.widgets.app_setting.app_setting_flyout import AppSettingFlyout
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.teaching_tip import TeachingTip


class AppNotifySettingFlyout(FlyoutViewBase):
    """单个应用的通知设置弹出框。"""

    _current_tip: ClassVar[TeachingTip | None] = None

    def __init__(
        self,
        ctx: OneDragonContext,
        app_id: str,
        app_name: str,
        parent: QWidget | None = None,
    ) -> None:
        FlyoutViewBase.__init__(self, parent)
        self.ctx: OneDragonContext = ctx
        self.app_id: str = app_id
        self.app_name: str = app_name
        self.card_margins = Margins(8, 4, 0, 8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title_label = SubtitleLabel(gt(app_name), self)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        self.lifecycle_opt = ComboBoxSettingCard(
            icon='',
            title='应用通知',
            margins=self.card_margins,
            options_enum=NotifyLifecycleMode,
        )
        self.detail_opt = ComboBoxSettingCard(
            icon='',
            title='节点通知',
            margins=self.card_margins,
            options_enum=NotifyDetailMode,
        )
        self.lifecycle_opt.setFixedWidth(360)
        self.detail_opt.setFixedWidth(360)
        self.lifecycle_opt.combo_box.setFixedWidth(148)
        self.detail_opt.combo_box.setFixedWidth(148)
        layout.addWidget(self.lifecycle_opt)
        layout.addWidget(self.detail_opt)

        for card in self.findChildren(SettingCard):
            card.paintEvent = lambda _e: None

    def backgroundColor(self) -> QColor:
        return QColor(0, 0, 0, 0)

    def borderColor(self) -> QColor:
        return QColor(0, 0, 0, 0)

    def init_config(self) -> None:
        """初始化配置显示。"""
        self.lifecycle_opt.setValue(
            self.ctx.notify_config.get_app_lifecycle_mode(self.app_id),
            emit_signal=False,
        )
        self.detail_opt.setValue(
            self.ctx.notify_config.get_app_detail_mode(self.app_id),
            emit_signal=False,
        )
        self.lifecycle_opt.value_changed.connect(self._on_lifecycle_changed)
        self.detail_opt.value_changed.connect(self._on_detail_changed)

    def _on_lifecycle_changed(self, _idx: int, value: str) -> None:
        """应用通知模式变更。"""
        self.ctx.notify_config.set_app_lifecycle_mode(self.app_id, value)

    def _on_detail_changed(self, _idx: int, value: str) -> None:
        """节点通知模式变更。"""
        self.ctx.notify_config.set_app_detail_mode(self.app_id, value)

    @classmethod
    def show_flyout(
        cls,
        ctx: OneDragonContext,
        app_id: str,
        app_name: str,
        target: QWidget,
        parent: QWidget | None = None,
    ) -> TeachingTip:
        """显示应用通知设置弹出框。"""
        prev = AppNotifySettingFlyout._current_tip or AppSettingFlyout._current_tip
        if prev is not None:
            try:
                if prev.isVisible():
                    prev.close()
            except RuntimeError:
                pass
            AppNotifySettingFlyout._current_tip = None
            AppSettingFlyout._current_tip = None

        content_view = cls(ctx, app_id, app_name, parent)
        content_view.init_config()

        tip = TeachingTip.make(
            view=content_view,
            target=target,
            duration=-1,
            tailPosition=TeachingTipTailPosition.RIGHT,
            parent=parent,
        )

        AppNotifySettingFlyout._current_tip = tip
        AppSettingFlyout._current_tip = tip
        tip.destroyed.connect(lambda: setattr(AppNotifySettingFlyout, '_current_tip', None))
        tip.destroyed.connect(lambda: setattr(AppSettingFlyout, '_current_tip', None))
        return tip
