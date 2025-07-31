from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy


class Column(QWidget):
    """
    垂直布局容器组件，用于将多个组件在垂直方向上排列。
    支持在创建时自定义间距和边距。

    Usage:
        # 基本用法
        column = Column()
        column.add_widget(button1)
        column.add_widget(button2)

        # 自定义间距和边距
        column = Column(spacing=8, margins=(10, 5, 10, 5))

    Args:
        parent: 父组件，默认为None
        spacing: 组件之间的间距，单位为像素
        margins: 容器的边距，支持4个值(left,top,right,bottom)、2个值(horizontal,vertical)或1个值
    """

    def __init__(self, parent=None, spacing: int | None = None, margins: tuple | int | None = None):
        QWidget.__init__(self, parent=parent)

        self.v_layout = QVBoxLayout(self)

        if spacing is not None:
            self.v_layout.setSpacing(spacing)

        if margins is not None:
            if len(margins) == 4:
                # (left, top, right, bottom)
                self.v_layout.setContentsMargins(margins[0], margins[1], margins[2], margins[3])
            elif len(margins) == 2:
                # (horizontal, vertical)
                self.v_layout.setContentsMargins(margins[0], margins[1], margins[0], margins[1])
            elif len(margins) == 1:
                # uniform margin
                margin = margins[0]
                self.v_layout.setContentsMargins(margin, margin, margin, margin)

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
