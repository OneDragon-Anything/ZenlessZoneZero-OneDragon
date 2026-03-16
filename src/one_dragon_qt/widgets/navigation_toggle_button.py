from collections.abc import Callable

from qfluentwidgets import (
    FluentIconBase,
    NavigationBarPushButton,
    NavigationItemPosition,
)


class NavigationToggleButton(NavigationBarPushButton):
    """导航栏上的非页面切换按钮。"""

    def __init__(
        self,
        route_key: str,
        text: str,
        icon_off: FluentIconBase,
        icon_on: FluentIconBase,
        tooltip_off: str,
        tooltip_on: str,
        on_click: Callable[[], None],
        position: NavigationItemPosition = NavigationItemPosition.TOP,
        parent=None,
    ) -> None:
        super().__init__(icon_off, text, False, parent)

        self._route_key = route_key
        self._icon_off = icon_off
        self._icon_on = icon_on
        self._tooltip_off = tooltip_off
        self._tooltip_on = tooltip_on
        self._on_click = on_click
        self._position = position
        self._active = False
        self._attached = False
        self.setToolTip(tooltip_off)

    def attach_to(self, navigation) -> None:
        if self._attached:
            return

        navigation.insertWidget(
            len(navigation.items),
            self._route_key,
            self,
            self._on_click,
            self._position,
        )
        self._attached = True
        self.set_active(self._active)

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
