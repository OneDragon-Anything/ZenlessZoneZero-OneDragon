from typing import NamedTuple

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget


class Margins(NamedTuple):
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0


class IconSize(NamedTuple):
    width: int = 0
    height: int = 0


def apply_shadow(widget: QWidget, blur: int = 5, offset_x: int = 0, offset_y: int = 0, alpha: int = 255) -> None:
    """为控件添加阴影效果"""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(offset_x, offset_y)
    shadow.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(shadow)
