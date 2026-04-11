from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import PopUpAniStackedWidget

from one_dragon_qt.widgets.base_interface import BaseInterface


class PageStackWrapper(QWidget):
    """包装一个子界面，支持推入/弹出二级设置界面。返回按钮由外部提供。"""

    def __init__(self, sub_interface: BaseInterface, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(sub_interface.objectName())
        self._sub_interface = sub_interface
        self._secondary_content: QWidget | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 内层页面栈：page0=子界面, page1=二级设置
        self._page_stack = PopUpAniStackedWidget(self)
        self._page_stack.setContentsMargins(0, 0, 0, 0)
        self._page_stack.addWidget(sub_interface)
        layout.addWidget(self._page_stack)

    @property
    def is_secondary_shown(self) -> bool:
        return self._page_stack.currentWidget() is not self._sub_interface

    def push_setting(self, title: str, content: QWidget) -> None:
        self._sub_interface.on_interface_hidden()
        self._clear_secondary()
        self._secondary_content = content
        self._page_stack.addWidget(content, deltaX=80, deltaY=0)
        self._page_stack.setCurrentWidget(content, duration=200)
        if isinstance(content, BaseInterface):
            content.on_interface_shown()

    def reset_to_root(self) -> None:
        """重置到根页面，清除二级设置界面。"""
        if not self.is_secondary_shown:
            return
        if isinstance(self._secondary_content, BaseInterface):
            self._secondary_content.on_interface_hidden()
        self._page_stack.setCurrentWidget(self._sub_interface, duration=0)
        self._clear_secondary()
        self._sub_interface.on_interface_shown()

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

    def _clear_secondary(self) -> None:
        if self._secondary_content is not None:
            self._page_stack.removeWidget(self._secondary_content)
            self._secondary_content.setParent(None)
            self._secondary_content = None
