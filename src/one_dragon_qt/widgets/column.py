from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout


class Column(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.v_layout = QVBoxLayout(self)
        # 维护子控件列表，便于拖拽排序等场景访问
        self.widgets: list[QWidget] = []

    def add_widget(self, widget: QWidget, stretch: int = 0, alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignTop):
        self.v_layout.addWidget(widget, stretch=stretch, alignment=alignment)
        if widget not in self.widgets:
            self.widgets.append(widget)

    def remove_widget(self, widget: QWidget):
        self.v_layout.removeWidget(widget)
        if widget in self.widgets:
            self.widgets.remove(widget)

    def add_stretch(self, stretch: int):
        self.v_layout.addStretch(stretch)

    def clear_widgets(self) -> None:
        while self.v_layout.count():
            child = self.v_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.widgets.clear()
