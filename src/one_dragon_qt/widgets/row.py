from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

from one_dragon_qt.utils.layout_utils import Margins


class Row(QWidget):
    """
    水平布局容器组件，用于将多个组件在水平方向上排列。

    Usage:
        row = Row(spacing=8, margins=Margins(10, 5, 10, 5))
        row.add_widget(button1)
    """

    def __init__(self, parent=None, spacing: int | None = None, margins: Margins | None = None):
        QWidget.__init__(self, parent=parent)

        self.h_layout = QHBoxLayout(self)

        if spacing is not None:
            self.h_layout.setSpacing(spacing)

        if margins is not None:
            self.h_layout.setContentsMargins(margins.left, margins.top, margins.right, margins.bottom)

    def add_widget(self, widget: QWidget, stretch: int = 0, alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft):
        self.h_layout.addWidget(widget, stretch=stretch, alignment=alignment)

    def add_stretch(self, stretch: int):
        self.h_layout.addStretch(stretch)
