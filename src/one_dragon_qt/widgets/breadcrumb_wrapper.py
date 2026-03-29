from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import BreadcrumbBar, setFont

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
