from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter
from qfluentwidgets import FluentIcon, FluentIconBase, drawIcon, themeColor

from one_dragon_qt.widgets.navigation_button import NavigationToggleButton


class BackNavigationButton(NavigationToggleButton):
    """导航栏上的返回按钮。紧凑尺寸，平时禁用外观，激活时强调色背景 + 白色图标。"""

    def __init__(self, on_click, parent=None) -> None:
        super().__init__(
            object_name='back_nav_btn',
            text='',
            icon_off=FluentIcon.RETURN,
            icon_on=FluentIcon.RETURN,
            tooltip_off='',
            tooltip_on='返回',
            on_click=on_click,
            parent=parent,
        )
        self._isSelectedTextVisible = False
        self.setFixedSize(64, 36)

    def _drawBackground(self, painter: QPainter) -> None:
        if self._active:
            # 基础强调色背景
            painter.setBrush(themeColor())
            painter.drawRoundedRect(self.rect(), 5, 5)
            # 悬停/按下时叠加半透明层（仿 PrimaryPushButton）
            if self.isPressed:
                painter.setBrush(QColor(0, 0, 0, 30))
                painter.drawRoundedRect(self.rect(), 5, 5)
            elif self.isEnter:
                painter.setBrush(QColor(255, 255, 255, 30))
                painter.drawRoundedRect(self.rect(), 5, 5)
        # 非 active 视为禁用，不绘制任何背景

    def _drawIcon(self, painter: QPainter) -> None:
        if not self._active:
            painter.setOpacity(0.4)

        # 图标居中（无文字）
        icon_size = 20
        x = (self.width() - icon_size) / 2
        y = (self.height() - icon_size) / 2
        rect = QRectF(x, y, icon_size, icon_size)

        icon = self._icon
        if self._active:
            # active: 白色图标 on 强调色背景
            if isinstance(icon, FluentIconBase):
                icon.render(painter, rect, fill='white')
            else:
                drawIcon(icon, painter, rect)
        else:
            drawIcon(icon, painter, rect)

    def _drawText(self, painter: QPainter) -> None:
        pass
