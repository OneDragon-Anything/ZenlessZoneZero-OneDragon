from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import BreadcrumbBar, FluentIconBase, Pivot, qrouter, setFont

from one_dragon_qt.widgets.base_interface import BaseInterface


class BreadcrumbWrapper(QWidget):
    """包装一个子界面，在其上方添加面包屑导航，支持推入二级设置界面。"""

    def __init__(self, sub_interface: BaseInterface, root_text: str = '', parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(sub_interface.objectName())
        self._sub_interface = sub_interface
        self._secondary_content: QWidget | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 面包屑
        bc_wrapper = QWidget(self)
        bc_layout = QVBoxLayout(bc_wrapper)
        bc_layout.setContentsMargins(20, 8, 11, 8)
        bc_layout.setSpacing(0)

        self._breadcrumb = BreadcrumbBar(bc_wrapper)
        setFont(self._breadcrumb, 18)
        self._breadcrumb.setSpacing(12)
        self._breadcrumb.addItem('__root__', root_text or sub_interface.nav_text)
        self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_clicked)
        bc_layout.addWidget(self._breadcrumb)
        layout.addWidget(bc_wrapper)

        bc_wrapper.setVisible(False)
        self._bc_wrapper = bc_wrapper

        # 内层页面栈：page0=子界面, page1=二级设置
        self._page_stack = QStackedWidget(self)
        self._page_stack.addWidget(sub_interface)
        layout.addWidget(self._page_stack)

    @property
    def is_secondary_shown(self) -> bool:
        return self._page_stack.currentWidget() is not self._sub_interface

    def push_setting(self, title: str, content: QWidget) -> None:
        self._sub_interface.on_interface_hidden()
        self._clear_secondary()
        self._secondary_content = content
        self._page_stack.addWidget(content)
        self._breadcrumb.addItem('__setting__', title)
        self._page_stack.setContentsMargins(9, 0, 0, 0)
        self._bc_wrapper.setVisible(True)

    def reset_to_root(self) -> None:
        """重置到根页面，清除二级设置界面。"""
        if not self.is_secondary_shown:
            return
        self._on_breadcrumb_clicked('__root__')

    def on_interface_shown(self) -> None:
        if self.is_secondary_shown:
            if isinstance(self._secondary_content, BaseInterface):
                self._secondary_content.on_interface_shown()
        else:
            self._sub_interface.on_interface_shown()

    def on_interface_hidden(self) -> None:
        if self.is_secondary_shown:
            if isinstance(self._secondary_content, BaseInterface):
                self._secondary_content.on_interface_hidden()
        else:
            self._sub_interface.on_interface_hidden()

    def _on_breadcrumb_clicked(self, route_key: str) -> None:
        if route_key == '__root__':
            if not self.is_secondary_shown:
                return
            if isinstance(self._secondary_content, BaseInterface):
                self._secondary_content.on_interface_hidden()
            self._page_stack.setCurrentWidget(self._sub_interface)
            self._clear_secondary()
            self._bc_wrapper.setVisible(False)
            self._sub_interface.on_interface_shown()
        elif route_key == '__setting__' and self._secondary_content is not None:
            self._page_stack.setCurrentWidget(self._secondary_content)
            if isinstance(self._secondary_content, BaseInterface):
                self._secondary_content.on_interface_shown()

    def _clear_secondary(self) -> None:
        if self._secondary_content is not None:
            self._page_stack.removeWidget(self._secondary_content)
            self._secondary_content.setParent(None)
            self._page_stack.setContentsMargins(0, 0, 0, 0)
            self._secondary_content = None


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
        self._breadcrumb_wrappers: dict[str, BreadcrumbWrapper] = {}

        self.v_box_layout.addWidget(self.pivot, 0, Qt.AlignmentFlag.AlignLeft)
        self.v_box_layout.addWidget(self.stacked_widget)

        self.create_sub_interface()
        qrouter.setDefaultRouteKey(self.stacked_widget, self.stacked_widget.currentWidget().objectName())
        self.stacked_widget.currentChanged.connect(self.on_current_index_changed)

    def add_sub_interface(self, sub_interface: BaseInterface,
                          enable_breadcrumb: bool = False, breadcrumb_root_text: str = ''):
        if enable_breadcrumb:
            root_text = breadcrumb_root_text or sub_interface.nav_text
            wrapper = BreadcrumbWrapper(sub_interface, root_text, self.stacked_widget)
            self._breadcrumb_wrappers[sub_interface.objectName()] = wrapper
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

    def on_current_index_changed(self, index):
        if index != self._last_stack_idx:
            last_widget = self.stacked_widget.widget(self._last_stack_idx)
            if isinstance(last_widget, BreadcrumbWrapper | BaseInterface):
                last_widget.on_interface_hidden()
            self._last_stack_idx = index

        current_widget = self.stacked_widget.widget(index)
        self.pivot.setCurrentItem(current_widget.objectName())
        qrouter.push(self.stacked_widget, current_widget.objectName())
        if isinstance(current_widget, BreadcrumbWrapper | BaseInterface):
            current_widget.on_interface_shown()

    def on_interface_shown(self) -> None:
        """子界面显示时 进行初始化"""
        current_widget = self.stacked_widget.currentWidget()
        if isinstance(current_widget, BreadcrumbWrapper | BaseInterface):
            current_widget.on_interface_shown()

    def on_interface_hidden(self) -> None:
        """子界面隐藏时的回调"""
        current_widget = self.stacked_widget.currentWidget()
        if isinstance(current_widget, BreadcrumbWrapper | BaseInterface):
            current_widget.on_interface_hidden()

    def push_setting_interface(self, title: str, content: QWidget) -> None:
        """在当前子页面的面包屑包装中推入二级设置界面。"""
        current_widget = self.stacked_widget.currentWidget()
        if isinstance(current_widget, BreadcrumbWrapper):
            current_widget.push_setting(title, content)
