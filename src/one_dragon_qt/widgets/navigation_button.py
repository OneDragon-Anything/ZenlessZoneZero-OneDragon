from collections.abc import Callable

from PySide6.QtGui import QPainter
from qfluentwidgets import FluentIconBase, NavigationBarPushButton


class NavigationButton(NavigationBarPushButton):
    """导航栏自定义按钮的基类。

    子类需要：
    - 设置 objectName 作为 route_key
    - 设置 on_click 作为点击回调
    """

    def __init__(
        self,
        object_name: str,
        text: str,
        icon: FluentIconBase,
        on_click: Callable[[], None],
        parent=None,
    ) -> None:
        super().__init__(icon, text, False, parent)
        self.setObjectName(object_name)
        self.on_click = on_click


class NavigationToggleButton(NavigationButton):
    """导航栏上带开关状态的按钮。"""

    def __init__(
        self,
        object_name: str,
        text: str,
        icon_off: FluentIconBase,
        icon_on: FluentIconBase,
        tooltip_off: str,
        tooltip_on: str,
        on_click: Callable[[], None],
        parent=None,
    ) -> None:
        super().__init__(object_name, text, icon_off, on_click, parent)

        self._icon_off = icon_off
        self._icon_on = icon_on
        self._tooltip_off = tooltip_off
        self._tooltip_on = tooltip_on
        self._active = False
        self.setToolTip(tooltip_off)

    @property
    def active(self) -> bool:
        return self._active

    def set_active(self, active: bool) -> None:
        self._active = active
        icon = self._icon_on if active else self._icon_off
        tooltip = self._tooltip_on if active else self._tooltip_off
        self._icon = icon
        self._selectedIcon = icon
        self.setToolTip(tooltip)
        self.update()

    def _drawIcon(self, painter: QPainter) -> None:
        if self._active:
            old = self.isSelected
            self.isSelected = True
            super()._drawIcon(painter)
            self.isSelected = old
        else:
            super()._drawIcon(painter)

    def _drawText(self, painter: QPainter) -> None:
        if self._active:
            old = self.isSelected
            self.isSelected = True
            super()._drawText(painter)
            self.isSelected = old
        else:
            super()._drawText(painter)
