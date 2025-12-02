from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget
from qfluentwidgets import Pivot, qrouter
from qfluentwidgets.window.stacked_widget import StackedWidget

from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon_qt.windows.window import PhosStackedWidget


class PivotNavigatorDialog(QDialog):
    """带导航功能的弹窗对话框"""

    def __init__(
        self,
        title: str,
        parent=None
    ):
        """
        Args:
            title: 对话框标题
            parent: 父窗口
        """
        super().__init__(parent=parent)

        self.setWindowTitle(title)

        # 创建导航和内容区域
        self.pivot: Pivot | None = None
        self.stacked_widget: StackedWidget | None = None
        self._last_stack_idx: int = 0
        self.v_box_layout: QVBoxLayout | None = None

        self._layout_inited: bool = False  # 标记是否已经初始化过布局

    def show_with_parent(self, parent: QWidget) -> None:
        self.setParent(parent, Qt.WindowType.Dialog)
        self.init_layout()
        self.show()
        self.on_dialog_shown()

    def init_layout(self):
        """设置对话框的基本样式和布局"""
        if self._layout_inited:
            return

        # 启用最大化按钮
        flags = self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint
        self.setWindowFlags(flags)

        # 初始化导航
        self.pivot = Pivot(self)
        self.stacked_widget = PhosStackedWidget(self)
        self.create_sub_interface()

        # 设置默认路由
        if self.stacked_widget.currentWidget() is not None:
            qrouter.setDefaultRouteKey(self.stacked_widget, self.stacked_widget.currentWidget().objectName())

        self.stacked_widget.currentChanged.connect(self.on_current_index_changed)

        # 添加垂直布局到对话框主体
        self.v_box_layout = QVBoxLayout(self)

        # 添加导航栏和堆叠窗口
        self.v_box_layout.addWidget(self.pivot, 0, Qt.AlignmentFlag.AlignLeft)
        self.v_box_layout.addWidget(self.stacked_widget)

        # 设置边距
        self.v_box_layout.setContentsMargins(20, 20, 20, 20)

        # 设置对话框大小
        self.setMinimumSize(800, 600)

        # 样式
        OdQtStyleSheet.STACKED_WIDGET.apply(self.stacked_widget)
        OdQtStyleSheet.DIALOG.apply(self)

        self._layout_inited = True

    def add_sub_interface(self, sub_interface: BaseInterface):
        """
        添加子界面到导航对话框

        Args:
            sub_interface: 要添加的子界面
        """
        self.stacked_widget.addWidget(sub_interface)

        if self.pivot is not None:
            self.pivot.addItem(
                routeKey=sub_interface.objectName(),
                text=sub_interface.nav_text,
                onClick=lambda: self.stacked_widget.setCurrentWidget(sub_interface)
            )

        if self.stacked_widget.currentWidget() is None:
            self.stacked_widget.setCurrentWidget(sub_interface)

        if self.pivot is not None and self.pivot.currentItem() is None:
            self.pivot.setCurrentItem(sub_interface.objectName())

    def create_sub_interface(self):
        """
        创建下面的子页面 - 由子类实现
        """
        pass

    def on_current_index_changed(self, index: int):
        """当前页面索引改变时的回调"""
        if index != self._last_stack_idx:
            last_interface = self.stacked_widget.widget(self._last_stack_idx)
            if isinstance(last_interface, BaseInterface):
                last_interface.on_interface_hidden()
            self._last_stack_idx = index

        current_interface = self.stacked_widget.widget(index)
        if self.pivot is not None:
            self.pivot.setCurrentItem(current_interface.objectName())
            qrouter.push(self.stacked_widget, current_interface.objectName())

        if isinstance(current_interface, BaseInterface):
            current_interface.on_interface_shown()

    def on_dialog_shown(self) -> None:
        """对话框显示时进行初始化"""
        if self.stacked_widget.currentWidget():
            self.stacked_widget.currentWidget().on_interface_shown()

    def on_dialog_hidden(self) -> None:
        """对话框隐藏时的回调"""
        if self.stacked_widget.currentWidget():
            self.stacked_widget.currentWidget().on_interface_hidden()
