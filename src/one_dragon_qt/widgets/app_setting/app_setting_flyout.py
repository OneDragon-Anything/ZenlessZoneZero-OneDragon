from __future__ import annotations

from typing import ClassVar

from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (
    FlyoutViewBase,
    SettingCard,
    TeachingTip,
    TeachingTipTailPosition,
)

from one_dragon_qt.widgets.fixed_teaching_tip import FixedTeachingTip


class AppSettingFlyout(FlyoutViewBase):
    """应用配置弹出框基类。

    子类需实现:
    - ``_setup_ui(layout)``: 往 QVBoxLayout 中添加控件。
    - ``init_config()``: 读取配置并初始化控件值。
    """

    _current_tip: ClassVar[TeachingTip | None] = None

    def __init__(self, ctx, group_id: str, parent=None):
        FlyoutViewBase.__init__(self, parent)
        self.ctx = ctx
        self.group_id = group_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        self._setup_ui(layout)

        # 去掉 SettingCard 在 flyout 中多余的卡片边框和背景
        for card in self.findChildren(SettingCard):
            card.paintEvent = lambda _e: None

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
        if cls._current_tip is not None:
            try:
                if cls._current_tip.isVisible():
                    return cls._current_tip
            except RuntimeError:
                pass
            cls._current_tip = None

        content_view = cls(ctx, group_id, parent)
        content_view.init_config()

        tip = FixedTeachingTip.make(
            view=content_view,
            target=target,
            duration=-1,
            tailPosition=TeachingTipTailPosition.RIGHT,
            parent=parent,
        )

        cls._current_tip = tip
        tip.destroyed.connect(lambda: setattr(cls, '_current_tip', None))
        return tip
