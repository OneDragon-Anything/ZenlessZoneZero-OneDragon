from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from one_dragon_qt.utils.layout_utils import Margins


class Column(QWidget):
    """
    垂直布局容器组件，用于将多个组件在垂直方向上排列。

    Usage:
        column = Column(spacing=8, margins=Margins(10, 5, 10, 5))
        column.add_widget(button1)
    """

    def __init__(self, parent=None, spacing: int | None = None, margins: Margins | None = None):
        QWidget.__init__(self, parent=parent)

        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(0, 0, 0, 0)

        if spacing is not None:
            self.v_layout.setSpacing(spacing)

        if margins is not None:
            self.v_layout.setContentsMargins(margins.left, margins.top, margins.right, margins.bottom)

    def add_widget(self, widget: QWidget, stretch: int = 0, alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignTop):
        self.v_layout.addWidget(widget, stretch=stretch, alignment=alignment)

    def remove_widget(self, widget: QWidget):
        self.v_layout.removeWidget(widget)

    def add_stretch(self, stretch: int):
        self.v_layout.addStretch(stretch)

    def clear_widgets(self) -> None:
        while self.v_layout.count():
            child = self.v_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
