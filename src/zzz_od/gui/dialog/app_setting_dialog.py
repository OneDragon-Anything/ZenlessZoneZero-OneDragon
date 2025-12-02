from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget
from qfluentwidgets import SingleDirectionScrollArea

from one_dragon.base.operation.application import application_const

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class AppSettingDialog(QDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.ctx: ZContext = ctx
        self.group_id: str = application_const.DEFAULT_GROUP_ID

        self._layout_inited: bool = False  # 布局是否已经完成初始化

    def show_by_group(self, group_id: str, parent: QWidget) -> None:
        self.group_id = group_id
        self.setParent(parent, Qt.WindowType.Dialog)
        self.init_layout()
        self.show()
        self.on_dialog_shown()

    def init_layout(self) -> None:
        """
        初始化弹窗的布局，默认是垂直方向的滚动布局
        """
        if self._layout_inited:
            return

        # 创建一个垂直布局
        main_layout = QVBoxLayout(self)
        scroll_area = SingleDirectionScrollArea(orient=Qt.Orientation.Vertical)
        main_layout.addWidget(scroll_area, stretch=0)

        content_widget = self.get_content_widget()
        content_widget.setStyleSheet("QWidget { background-color: transparent; }")
        scroll_area.setWidget(content_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        self._layout_inited = True

    def get_content_widget(self) -> QWidget:
        """
        子类实现 获取弹窗中具体的内容组件

        Returns:
            QWidget: 内容组件
        """
        pass

    def on_dialog_shown(self) -> None:
        """
        弹窗显示时进行的初始化 由子类实现
        """
        pass