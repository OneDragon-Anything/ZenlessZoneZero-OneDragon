from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSizePolicy


class Row(QWidget):
    """
    水平布局容器组件，用于将多个组件在水平方向上排列。
    支持在创建时自定义间距和边距。

    Usage:
        # 基本用法
        row = Row()
        row.add_widget(button1)
        row.add_widget(button2)

        # 自定义间距和边距
        row = Row(spacing=8, margins=(10, 5, 10, 5))

    Args:
        parent: 父组件，默认为None
        spacing: 组件之间的间距，单位为像素
        margins: 容器的边距，支持4个值(left,top,right,bottom)、2个值(horizontal,vertical)或1个值
    """

    def __init__(self, parent=None, spacing: int | None = None, margins: tuple | int | None = None):
        QWidget.__init__(self, parent=parent)

        self.h_layout = QHBoxLayout(self)

        if spacing is not None:
            self.h_layout.setSpacing(spacing)

        if margins is not None:
            # 支持 int、tuple、list，避免对 int 执行 len() 触发 TypeError
            if isinstance(margins, int):
                l = t = r = b = int(margins)
            elif isinstance(margins, (tuple, list)):
                if len(margins) == 4:
                    l, t, r, b = map(int, margins)
                elif len(margins) == 2:
                    h, v = map(int, margins)
                    l = r = h
                    t = b = v
                elif len(margins) == 1:
                    l = t = r = b = int(margins[0])
                else:
                    raise ValueError("margins 只能为 1/2/4 个整数")
            else:
                raise TypeError("margins 类型应为 int 或 tuple/list[int]")
            self.h_layout.setContentsMargins(l, t, r, b)

    def add_widget(self, widget: QWidget, stretch: int = 0, alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft):
        self.h_layout.addWidget(widget, stretch=stretch, alignment=alignment)

    def add_stretch(self, stretch: int):
        self.h_layout.addStretch(stretch)
