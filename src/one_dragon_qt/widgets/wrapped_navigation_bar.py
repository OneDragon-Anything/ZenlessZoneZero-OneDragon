from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    FluentIconBase,
    NavigationBar,
    NavigationBarPushButton,
    NavigationItemPosition,
    isDarkTheme,
)
from qfluentwidgets.common.color import autoFallbackThemeColor
from qfluentwidgets.common.icon import drawIcon

from one_dragon.utils.i18_utils import get_default_lang


NAVIGATION_ITEM_WIDTH = 64
NAVIGATION_ITEM_HEIGHT = 58
_COMPACT_ENGLISH_LABELS = {
    'Dashboard': 'Home',
    'Game Assistant': 'Game\nHelp',
    'OneDragon': 'One\nDragon',
    'App Runner': 'App\nRun',
    'Picture in Picture': 'PiP\nMode',
    'Developer Tools': 'Dev\nTools',
    'Code Sync': 'Code\nSync',
    'Account Management': 'User\nData',
    'Settings': 'Setup',
}


class WrappedNavigationBarPushButton(NavigationBarPushButton):
    """Navigation button that keeps translated labels inside the sidebar."""

    def __init__(
        self,
        icon: str | QIcon | FluentIconBase,
        text: str,
        is_selectable: bool,
        selected_icon: str | QIcon | FluentIconBase | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize a compact navigation button with localized text wrapping."""
        super().__init__(
            icon=icon,
            text=text,
            isSelectable=is_selectable,
            selectedIcon=selected_icon,
            parent=parent,
        )
        self.setFixedSize(NAVIGATION_ITEM_WIDTH, NAVIGATION_ITEM_HEIGHT)
        font = self.font()
        font.setPixelSize(10)
        font.setStretch(100)
        self.setFont(font)
        self.setText(text)

    def setText(self, text: str) -> None:
        """Split long localized navigation labels into two compact lines."""
        super().setText(self._wrap_label(text))

    @staticmethod
    def _wrap_label(text: str) -> str:
        """Return a compact one- or two-line navigation label."""
        if get_default_lang() == 'en':
            compact_text = _COMPACT_ENGLISH_LABELS.get(text)
            if compact_text is not None:
                return compact_text

        if '\n' in text or ' ' not in text:
            return text

        words = text.split()
        if len(words) == 2:
            return f'{words[0]}\n{words[1]}'
        return f'{words[0]}\n{" ".join(words[1:])}'

    def _drawIcon(self, painter: QPainter) -> None:
        """Draw the navigation icon using the current interaction state."""
        if (self.isPressed or not self.isEnter) and not (self.isSelected or self.isAboutSelected):
            painter.setOpacity(0.6)
        if not self.isEnabled():
            painter.setOpacity(0.4)

        rect = QRectF((self.width() - 20) / 2, 5, 20, 20)
        selected_icon = self._selectedIcon or self._icon
        if isinstance(selected_icon, FluentIconBase) and (self.isSelected or self.isAboutSelected):
            color = autoFallbackThemeColor(self.lightSelectedColor, self.darkSelectedColor)
            selected_icon.render(painter, rect, fill=color.name())
        elif self.isSelected or self.isAboutSelected:
            drawIcon(selected_icon, painter, rect)
        else:
            drawIcon(self._icon, painter, rect)

    def _drawText(self, painter: QPainter) -> None:
        """Draw wrapped navigation text below the item icon."""
        if self.isSelected and not self._isSelectedTextVisible:
            return

        if self.isSelected or self.isAboutSelected:
            painter.setPen(autoFallbackThemeColor(self.lightSelectedColor, self.darkSelectedColor))
        else:
            painter.setPen(Qt.GlobalColor.white if isDarkTheme() else Qt.GlobalColor.black)

        painter.setFont(self.font())
        rect = QRect(2, 29, self.width() - 4, self.height() - 29)
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            self.text(),
        )


class WrappedNavigationBar(NavigationBar):
    """Navigation bar that only customizes localized item rendering."""

    def __init__(self, parent=None) -> None:
        """Initialize the navigation bar with standard Fluent behavior."""
        super().__init__(parent)

    def insertItem(
        self,
        index: int,
        route_key: str,
        icon: str | QIcon | FluentIconBase,
        text: str,
        on_click=None,
        selectable: bool = True,
        selected_icon=None,
        position: NavigationItemPosition = NavigationItemPosition.TOP,
    ) -> WrappedNavigationBarPushButton | None:
        """Insert a wrapped navigation item unless its route key already exists."""
        if route_key in self.items:
            return None

        widget = WrappedNavigationBarPushButton(
            icon,
            text,
            selectable,
            selected_icon,
            self,
        )
        widget.setSelectedColor(self.lightSelectedColor, self.darkSelectedColor)
        widget.setSelectedTextVisible(self.isSelectedTextVisible())
        self.insertWidget(index, route_key, widget, on_click, position)
        return widget
