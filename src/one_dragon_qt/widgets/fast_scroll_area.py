from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QWidget
from qfluentwidgets import ScrollArea as FluentScrollArea
from qfluentwidgets.common.smooth_scroll import SmoothMode


class FastScrollArea(FluentScrollArea):
    """项目默认滚动区域。

    统一封装项目页面级滚动区域，便于集中切换和验证不同滚动实现。
    当前使用实测最流畅的 qfluentwidgets.ScrollArea，并关闭平滑移动。
    """

    def __init__(
        self,
        orient: Qt.Orientation | None = Qt.Orientation.Vertical,
        parent: QWidget | None = None,
    ) -> None:
        FluentScrollArea.__init__(self, parent=parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self.set_scroll_orientation(orient)
        self.setSmoothMode(SmoothMode.NO_SMOOTH, Qt.Orientation.Vertical)
        self.setSmoothMode(SmoothMode.NO_SMOOTH, Qt.Orientation.Horizontal)

    def set_scroll_orientation(self, orient: Qt.Orientation | None) -> None:
        """设置主要滚动方向，None 表示双向滚动。"""
        if orient == Qt.Orientation.Vertical:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        elif orient == Qt.Orientation.Horizontal:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
