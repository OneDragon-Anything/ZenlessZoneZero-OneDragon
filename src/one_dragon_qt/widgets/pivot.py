from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QListView,
    QStyledItemDelegate,
    QHBoxLayout,
    QSizePolicy,
    QApplication,
    QStackedWidget,
    QVBoxLayout,
)
from qfluentwidgets import Pivot, ListItemDelegate, setFont, qrouter
from qfluentwidgets.common.animation import (
    FluentAnimation,
    FluentAnimationType,
    FluentAnimationProperty,
)
from qfluentwidgets.components.navigation.pivot import PivotItem

from one_dragon_qt.services.styles_manager import OdQtStyleSheet


class PhosPivot(Pivot):

    currentItemChanged = Signal(str)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.items = {}
        self._currentRouteKey = None

        self.hBoxLayout = QHBoxLayout(self)
        self.slideAni = FluentAnimation.create(
            FluentAnimationType.POINT_TO_POINT,
            FluentAnimationProperty.SCALE,
            value=0,
            parent=self,
        )

        OdQtStyleSheet.PIVOT.apply(self)

        self.hBoxLayout.setSpacing(30)  # 设置统一间距，替代手动添加spacer
        self.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

    def insertItem(self, index: int, routeKey: str, text: str, onClick=None, icon=None):
        if routeKey in self.items:
            return

        item = PhosPivotItem(text, self)
        if icon:
            item.setIcon(icon)
        item.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.insertWidget(index, routeKey, item, onClick)
        return item

    def insertWidget(self, index: int, routeKey: str, widget: PivotItem, onClick=None):
        if routeKey in self.items:
            return

        widget.setProperty("routeKey", routeKey)
        widget.itemClicked.connect(self._onItemClicked)
        if onClick:
            widget.itemClicked.connect(onClick)

        existing_count = len(self.items)
        self.items[routeKey] = widget

        # 使用setSpacing统一管理间距，无需手动添加spacer
        if index <= 0:
            self.hBoxLayout.insertWidget(0, widget, 0)
        elif index >= existing_count:
            self.hBoxLayout.addWidget(widget, 0)
        else:
            self.hBoxLayout.insertWidget(index, widget, 0)

    def paintEvent(self, e):
        QWidget().paintEvent(e)

        if not self.currentItem():
            return

        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f5d742"))

        x = int(self.currentItem().width() / 2 - 8 + self.slideAni.value())
        painter.drawRoundedRect(x, self.height() - 2, 16, 3, 1.5, 1.5)


class PhosPivotItem(PivotItem):
    """Pivot item"""

    itemClicked = Signal(bool)

    def _postInit(self):
        self.isSelected = False
        self.setProperty("isSelected", False)
        self.clicked.connect(lambda: self.itemClicked.emit(True))

        OdQtStyleSheet.PIVOT.apply(self)
        setFont(self, 18)

    def setSelected(self, isSelected: bool):
        if self.isSelected == isSelected:
            return

        self.isSelected = isSelected
        self.setProperty("isSelected", isSelected)
        self.setStyle(QApplication.style())
        self.update()


class CustomListItemDelegate(ListItemDelegate):
    def __init__(self, parent: QListView):
        super().__init__(parent)

    def paint(self, painter, option, index):
        QStyledItemDelegate(self).paint(painter, option, index)


class PivotNavigatorContainer(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.pivot = Pivot(self)
        self.stacked_widget = QStackedWidget(self)
        self.v_box_layout = QVBoxLayout(self)

        self.v_box_layout.addWidget(self.pivot, 0, Qt.AlignmentFlag.AlignLeft)
        self.v_box_layout.addWidget(self.stacked_widget)
        self.v_box_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget.currentChanged.connect(self.on_current_index_changed)

    def add_sub_interface(self, widget: QWidget, text: str):
        self.stacked_widget.addWidget(widget)
        self.pivot.addItem(
            routeKey=widget.objectName(),
            text=text,
            onClick=lambda: self.stacked_widget.setCurrentWidget(widget),
        )

        if self.stacked_widget.currentWidget() is None:
            self.stacked_widget.setCurrentWidget(widget)
        if self.pivot.currentItem() is None:
            self.pivot.setCurrentItem(widget.objectName())

    def on_current_index_changed(self, index):
        widget = self.stacked_widget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())
        qrouter.push(self.stacked_widget, widget.objectName())
