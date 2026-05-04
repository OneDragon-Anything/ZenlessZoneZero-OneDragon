from __future__ import annotations

from typing import ClassVar

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (
    FlyoutViewBase,
    SettingCard,
    TeachingTipTailPosition,
)

from one_dragon_qt.utils.layout_utils import Margins
from one_dragon_qt.widgets.teaching_tip import TeachingTip


class AppSettingFlyout(FlyoutViewBase):
    """应用配置弹出框基类。

    子类需实现:
    - ``_setup_ui(layout)``: 往 QVBoxLayout 中添加控件。
    - ``init_config()``: 读取配置并初始化控件值。

    基类提供 ``self.card_margins`` 供子类创建 SettingCard 时使用，
    并自动去掉所有 SettingCard 的边框背景。
    """

    _current_tip: ClassVar[TeachingTip | None] = None

    def __init__(self, ctx, group_id: str, parent=None):
        FlyoutViewBase.__init__(self, parent)
        self.ctx = ctx
        self.group_id = group_id
        self.card_margins = Margins(8, 4, 0, 8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        self._setup_ui(layout)

        # 去掉 SettingCard 在 flyout 中多余的卡片边框和背景
        for card in self.findChildren(SettingCard):
            card.paintEvent = lambda _e: None

    def backgroundColor(self) -> QColor:
        return QColor(0, 0, 0, 0)

    def borderColor(self) -> QColor:
        return QColor(0, 0, 0, 0)

    # ---------- 子类实现 ----------

    def _setup_ui(self, layout: QVBoxLayout) -> None:
        raise NotImplementedError

    def init_config(self) -> None:
        raise NotImplementedError

    # ---------- 统一显示逻辑 ----------

    @classmethod
    def show_flyout(
        cls,
        ctx,
        group_id: str,
        target: QWidget,
        parent: QWidget | None = None,
    ) -> TeachingTip:
        """显示配置弹出框，防止重复弹出。"""
        # 读取基类上的共享引用，确保所有子类互斥
        prev = AppSettingFlyout._current_tip
        if prev is not None:
            try:
                if prev.isVisible():
                    prev.close()
            except RuntimeError:
                pass
            AppSettingFlyout._current_tip = None

        content_view = cls(ctx, group_id, parent)
        content_view.init_config()

        tip = TeachingTip.make(
            view=content_view,
            target=target,
            duration=-1,
            tailPosition=TeachingTipTailPosition.RIGHT,
            parent=parent,
        )

        AppSettingFlyout._current_tip = tip
        tip.destroyed.connect(lambda: setattr(AppSettingFlyout, '_current_tip', None))
        return tip
