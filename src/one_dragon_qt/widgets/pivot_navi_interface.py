from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import FluentIconBase, Pivot, qrouter

from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon_qt.widgets.page_stack_wrapper import PageStackWrapper


class PivotNavigatorInterface(BaseInterface):

    # 当二级页面状态变化时发射：True=有二级页面, False=无
    secondary_state_changed = Signal(bool)

    def __init__(self,
                 object_name: str, nav_text_cn: str, nav_icon: FluentIconBase | QIcon | str,
                 parent=None,
                 ):
        BaseInterface.__init__(self, object_name=object_name, parent=parent,
                               nav_text_cn=nav_text_cn, nav_icon=nav_icon)

        self.v_box_layout = QVBoxLayout(self)
        self.v_box_layout.setSpacing(0)
        self.v_box_layout.setContentsMargins(0, 0, 0, 0)

        self.pivot = Pivot(self)
        self.stacked_widget = QStackedWidget(self)
        self._last_stack_idx: int = 0
        self._page_wrappers: dict[str, PageStackWrapper] = {}
        self._preload_started: bool = False
        self._preload_next_index: int = 0
        self._preload_include_current: bool = False

        self.v_box_layout.addWidget(self.pivot, 0, Qt.AlignmentFlag.AlignLeft)
        self.v_box_layout.addWidget(self.stacked_widget)

        self.create_sub_interface()
        qrouter.setDefaultRouteKey(self.stacked_widget, self.stacked_widget.currentWidget().objectName())
        self.stacked_widget.currentChanged.connect(self.on_current_index_changed)

    def add_sub_interface(self, sub_interface: BaseInterface,
                          enable_page_stack: bool = False) -> None:
        if enable_page_stack:
            wrapper = PageStackWrapper(sub_interface, self.stacked_widget)
            self._page_wrappers[sub_interface.objectName()] = wrapper
            actual_widget = wrapper
        else:
            actual_widget = sub_interface

        self.stacked_widget.addWidget(actual_widget)

        self.pivot.addItem(
            routeKey=sub_interface.objectName(),
            text=sub_interface.nav_text,
            onClick=lambda _checked=False, w=actual_widget: self.stacked_widget.setCurrentWidget(w),
        )

        if self.stacked_widget.currentWidget() is None:
            self.stacked_widget.setCurrentWidget(actual_widget)
        if self.pivot.currentItem() is None:
            self.pivot.setCurrentItem(sub_interface.objectName())

    def create_sub_interface(self):
        """
        创建下面的子页面
        :return:
        """
        pass

    def on_current_index_changed(self, index: int) -> None:
        current_widget = self.stacked_widget.widget(index)
        last_widget = self.stacked_widget.widget(self._last_stack_idx)

        if index != self._last_stack_idx:
            if isinstance(last_widget, PageStackWrapper | BaseInterface):
                last_widget.on_interface_hidden()
            self._last_stack_idx = index

        self.pivot.setCurrentItem(current_widget.objectName())
        qrouter.push(self.stacked_widget, current_widget.objectName())

        # 通知二级页面状态
        if isinstance(current_widget, PageStackWrapper):
            self.secondary_state_changed.emit(current_widget.is_secondary_shown)
        else:
            self.secondary_state_changed.emit(False)

        if isinstance(current_widget, PageStackWrapper | BaseInterface):
            current_widget.on_interface_shown()

    def on_interface_shown(self) -> None:
        """子界面显示时 进行初始化"""
        current_widget = self.stacked_widget.currentWidget()
        if isinstance(current_widget, PageStackWrapper | BaseInterface):
            current_widget.on_interface_shown()
        self._schedule_preload_sub_interfaces(delay_ms=200, include_current=False)

    def on_interface_hidden(self) -> None:
        """子界面隐藏时的回调"""
        current_widget = self.stacked_widget.currentWidget()
        if isinstance(current_widget, PageStackWrapper | BaseInterface):
            current_widget.on_interface_hidden()

    def push_setting_interface(self, title: str, content: QWidget) -> None:
        """在当前子页面的 PageStackWrapper 中推入二级设置界面。"""
        current_widget = self.stacked_widget.currentWidget()
        if isinstance(current_widget, PageStackWrapper):
            current_widget.push_setting(title, content)
            self.secondary_state_changed.emit(True)

    def pop_setting_interface(self) -> None:
        """重置当前子页面的 PageStackWrapper 到根页面。"""
        current_widget = self.stacked_widget.currentWidget()
        if isinstance(current_widget, PageStackWrapper):
            current_widget.reset_to_root()
            self.secondary_state_changed.emit(False)

    def preload_interface(self) -> None:
        """分帧预加载子标签页。"""
        BaseInterface.preload_interface(self)
        self._schedule_preload_sub_interfaces(delay_ms=0, include_current=True)

    def _schedule_preload_sub_interfaces(self, delay_ms: int, include_current: bool) -> None:
        if self._preload_started:
            return
        self._preload_started = True
        self._preload_next_index = 0
        self._preload_include_current = include_current
        QTimer.singleShot(delay_ms, self._preload_next_sub_interface)

    def _preload_next_sub_interface(self) -> None:
        while self._preload_next_index < self.stacked_widget.count():
            widget = self.stacked_widget.widget(self._preload_next_index)
            self._preload_next_index += 1
            if not self._preload_include_current and widget is self.stacked_widget.currentWidget():
                continue
            self._preload_widget(widget)
            QTimer.singleShot(80, self._preload_next_sub_interface)
            return

    def _preload_widget(self, widget: QWidget) -> None:
        if isinstance(widget, PageStackWrapper | BaseInterface):
            widget.preload_interface()
