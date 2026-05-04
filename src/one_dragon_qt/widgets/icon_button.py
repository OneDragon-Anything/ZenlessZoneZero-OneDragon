from PySide6.QtCore import QEvent
from PySide6.QtGui import QIcon
from qfluentwidgets import (
    FluentIconBase,
    TeachingTipTailPosition,
    TransparentToolButton,
)
from qfluentwidgets.common.overload import singledispatchmethod

from one_dragon_qt.widgets.teaching_tip import TeachingTip


class IconButton(TransparentToolButton):
    """包含下拉框的自定义设置卡片类。"""

    @singledispatchmethod
    def __init__(self, parent=None):
        TransparentToolButton.__init__(self, parent)

        self._tooltip: TeachingTip | None = None

    @__init__.register
    def _(self, icon: str | QIcon | FluentIconBase, parent=None):
        self.__init__(parent)
        self.setIcon(icon)

    @__init__.register
    def _(self, icon: str | QIcon | FluentIconBase,
          isTooltip: bool,
          tip_title: str,
          tip_content: str,
          parent=None):
        self.__init__(parent)
        self.setIcon(icon)

        # 处理工具提示
        if isTooltip:
            self.installEventFilter(self)

        self.tip_title: str = tip_title
        self.tip_content: str = tip_content

    def eventFilter(self, watched, event: QEvent) -> bool:
        """处理鼠标事件。"""
        if event.type() == QEvent.Type.Enter:
            self._show_tooltip()
        elif event.type() == QEvent.Type.Leave:
            self._hide_tooltip()
        return super().eventFilter(watched, event)

    def _show_tooltip(self) -> None:
        """显示工具提示。"""
        self._hide_tooltip()  # 先关闭已有的 tip
        self._tooltip = TeachingTip.create(
            target=self,
            title=self.tip_title,
            content=self.tip_content,
            tailPosition=TeachingTipTailPosition.RIGHT,
            isClosable=False,
            duration=-1,
            parent=self,
        )
        # 设置偏移
        if self._tooltip:
            tooltip_pos = self.mapToGlobal(self.rect().topRight())

            tooltip_pos.setX(tooltip_pos.x() - self._tooltip.size().width() - 40)  # 水平偏移
            tooltip_pos.setY(tooltip_pos.y() - self._tooltip.size().height() / 2 + 35)  # 垂直偏移

            self._tooltip.move(tooltip_pos)

    def _hide_tooltip(self) -> None:
        """隐藏工具提示。"""
        # 先置 None 防止 close() 触发事件时重入
        tip = self._tooltip
        self._tooltip = None
        if tip is not None:
            tip.close()

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self is other
