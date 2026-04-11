from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import SegmentedWidget

from one_dragon_qt.widgets.base_interface import BaseInterface


class SegmentedSettingInterface(BaseInterface):
    """多标签设置界面，使用 SegmentedWidget 切换子界面。"""

    def __init__(self, object_name: str, nav_text_cn: str,
                 sub_interfaces: list[BaseInterface], parent: QWidget | None = None) -> None:
        self.sub_interfaces = sub_interfaces
        BaseInterface.__init__(
            self,
            object_name=object_name,
            nav_text_cn=nav_text_cn,
            nav_icon='',
            parent=parent,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        segment_wrapper = QWidget(self)
        segment_layout = QVBoxLayout(segment_wrapper)
        segment_layout.setContentsMargins(11, 4, 11, 8)
        segment_layout.setSpacing(0)
        self._segment = SegmentedWidget(segment_wrapper)
        segment_layout.addWidget(self._segment, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(segment_wrapper)

        self._stacked = QStackedWidget(self)
        layout.addWidget(self._stacked)

        for iface in self.sub_interfaces:
            self._stacked.addWidget(iface)
            self._segment.addItem(
                routeKey=iface.objectName(),
                text=iface.nav_text,
                onClick=lambda checked=None, w=iface: self._switch_to(w),
            )

        if self.sub_interfaces:
            self._segment.setCurrentItem(self.sub_interfaces[0].objectName())

    def _switch_to(self, target: BaseInterface) -> None:
        current = self._stacked.currentWidget()
        if current is target:
            return
        if isinstance(current, BaseInterface):
            current.on_interface_hidden()
        self._stacked.setCurrentWidget(target)
        target.on_interface_shown()

    def on_interface_shown(self) -> None:
        current = self._stacked.currentWidget()
        if isinstance(current, BaseInterface):
            current.on_interface_shown()

    def on_interface_hidden(self) -> None:
        current = self._stacked.currentWidget()
        if isinstance(current, BaseInterface):
            current.on_interface_hidden()
