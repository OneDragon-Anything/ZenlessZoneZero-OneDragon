from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout
from qfluentwidgets import FluentIconBase, Pivot, qrouter

from one_dragon_qt.widgets.base_interface import BaseInterface


class PivotNavigatorInterface(BaseInterface):

    def __init__(self,
                 object_name: str, nav_text_cn: str, nav_icon: FluentIconBase | QIcon | str,
                 parent=None
                 ):
        BaseInterface.__init__(self, object_name=object_name, parent=parent,
                               nav_text_cn=nav_text_cn, nav_icon=nav_icon)

        self.pivot = Pivot(self)
        self.stacked_widget = QStackedWidget(self)
        self._last_stack_idx: int = 0
        self.v_box_layout = QVBoxLayout(self)
        self.v_box_layout.setSpacing(0)

        self.v_box_layout.addWidget(self.pivot, 0, Qt.AlignmentFlag.AlignLeft)
        self.v_box_layout.addWidget(self.stacked_widget)
        self.v_box_layout.setContentsMargins(0, 0, 0, 0)

        self.create_sub_interface()
        qrouter.setDefaultRouteKey(self.stacked_widget, self.stacked_widget.currentWidget().objectName())
        self.stacked_widget.currentChanged.connect(self.on_current_index_changed)

    def add_sub_interface(self, sub_interface: BaseInterface):
        self.stacked_widget.addWidget(sub_interface)
        self.pivot.addItem(
            routeKey=sub_interface.objectName(),
            text=sub_interface.nav_text,
            onClick=lambda: self.stacked_widget.setCurrentWidget(sub_interface)
        )

        if self.stacked_widget.currentWidget() is None:
            self.stacked_widget.setCurrentWidget(sub_interface)
        if self.pivot.currentItem() is None:
            self.pivot.setCurrentItem(sub_interface.objectName())

    def create_sub_interface(self):
        """
        创建下面的子页面
        :return:
        """
        pass

    def on_current_index_changed(self, index):
        if index != self._last_stack_idx:
            last_interface = self.stacked_widget.widget(self._last_stack_idx)
            if isinstance(last_interface, BaseInterface):
                last_interface.on_interface_hidden()
            self._last_stack_idx = index

        current_interface = self.stacked_widget.widget(index)
        self.pivot.setCurrentItem(current_interface.objectName())
        qrouter.push(self.stacked_widget, current_interface.objectName())
        if isinstance(current_interface, BaseInterface):
            current_interface.on_interface_shown()

    def on_interface_shown(self) -> None:
        """子界面显示时 进行初始化"""
        current_interface = self.stacked_widget.currentWidget()
        if isinstance(current_interface, BaseInterface):
            current_interface.on_interface_shown()

    def on_interface_hidden(self) -> None:
        """子界面隐藏时的回调"""
        current_interface = self.stacked_widget.currentWidget()
        if isinstance(current_interface, BaseInterface):
            current_interface.on_interface_hidden()
