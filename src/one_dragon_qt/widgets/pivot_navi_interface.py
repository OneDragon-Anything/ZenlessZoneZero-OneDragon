from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import FluentIconBase, Pivot, qrouter

from one_dragon_qt.widgets.base_interface import BaseInterface


class PivotNavigatorInterface(BaseInterface):

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
        self._dynamic_tab: QWidget | None = None  # 当前动态设置 Tab
        self._dynamic_route_key: str | None = None

        self.v_box_layout.addWidget(self.pivot, 0, Qt.AlignmentFlag.AlignLeft)
        self.v_box_layout.addSpacing(11)
        self.v_box_layout.addWidget(self.stacked_widget)

        self.create_sub_interface()
        qrouter.setDefaultRouteKey(self.stacked_widget, self.stacked_widget.currentWidget().objectName())
        self.stacked_widget.currentChanged.connect(self.on_current_index_changed)

    def add_sub_interface(self, sub_interface: BaseInterface) -> None:
        self.stacked_widget.addWidget(sub_interface)

        self.pivot.addItem(
            routeKey=sub_interface.objectName(),
            text=sub_interface.nav_text,
            onClick=lambda _checked=False, w=sub_interface: self.stacked_widget.setCurrentWidget(w),
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

    def on_current_index_changed(self, index: int) -> None:
        if index != self._last_stack_idx:
            last_widget = self.stacked_widget.widget(self._last_stack_idx)
            if isinstance(last_widget, BaseInterface):
                last_widget.on_interface_hidden()
            self._last_stack_idx = index

        current_widget = self.stacked_widget.widget(index)
        self.pivot.setCurrentItem(current_widget.objectName())
        qrouter.push(self.stacked_widget, current_widget.objectName())
        if isinstance(current_widget, BaseInterface):
            current_widget.on_interface_shown()

    def on_interface_shown(self) -> None:
        """子界面显示时 进行初始化"""
        current_widget = self.stacked_widget.currentWidget()
        if isinstance(current_widget, BaseInterface):
            current_widget.on_interface_shown()

    def on_interface_hidden(self) -> None:
        """子界面隐藏时的回调"""
        current_widget = self.stacked_widget.currentWidget()
        if isinstance(current_widget, BaseInterface):
            current_widget.on_interface_hidden()

    def push_setting_interface(self, title: str, content: QWidget) -> None:
        """动态添加一个设置 Tab 并切换到它；重复调用时替换内容，保留 PivotItem 避免动画异常。"""
        # 相同 content 直接切换
        if self._dynamic_tab is content:
            self.stacked_widget.setCurrentWidget(content)
            return

        # 替换旧 content（如有），保留 PivotItem
        if self._dynamic_tab is not None:
            old = self._dynamic_tab
            if isinstance(old, BaseInterface):
                old.on_interface_hidden()
            self.stacked_widget.blockSignals(True)
            self.stacked_widget.removeWidget(old)
            self._last_stack_idx = self.stacked_widget.currentIndex()
            self.stacked_widget.blockSignals(False)
            old.setParent(None)

        route_key = "_dynamic_setting"
        content.setObjectName(route_key)
        self._dynamic_tab = content
        self.stacked_widget.addWidget(content)

        if self._dynamic_route_key is None:
            # 首次：创建 PivotItem，lambda 通过 self._dynamic_tab 间接引用
            self._dynamic_route_key = route_key
            self.pivot.addItem(
                routeKey=route_key,
                text=title,
                onClick=lambda _checked=False: self._switch_to_dynamic_tab(),
            )
        else:
            # 已有 PivotItem，仅更新标题
            self.pivot.items[route_key].setText(title)

        # 强制布局重新计算，确保 PivotItem 的 geometry 已更新
        # 否则同一事件循环中 setCurrentWidget 触发动画时读取的 geometry 是旧的
        self.pivot.hBoxLayout.activate()
        self.stacked_widget.setCurrentWidget(content)

    def _switch_to_dynamic_tab(self) -> None:
        if self._dynamic_tab is not None:
            self.stacked_widget.setCurrentWidget(self._dynamic_tab)
