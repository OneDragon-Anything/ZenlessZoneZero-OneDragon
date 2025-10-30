from PySide6.QtGui import Qt, QIcon
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import FluentIconBase, SingleDirectionScrollArea
from typing import Union, Optional

from one_dragon_qt.widgets.base_interface import BaseInterface


class VerticalScrollInterface(BaseInterface):

    def __init__(self, content_widget: Optional[QWidget], object_name: str,
                 nav_text_cn: str, nav_icon: Union[FluentIconBase, QIcon, str] = None,
                 parent=None
                 ):
        """
        垂直方向上可滚动的子页面
        :param content_widget: 内容组件
        :param object_name: 导航用的唯一键
        :param nav_text_cn: 子页面在导航处显示的文本
        :param nav_icon: 子页面在导航处显示的图标
        :param parent:
        """
        BaseInterface.__init__(self, object_name=object_name, parent=parent,
                               nav_text_cn=nav_text_cn, nav_icon=nav_icon)

        self._param_content_widget: QWidget = content_widget
        self._init: bool = False  # 是否已经初始化了布局

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        BaseInterface.on_interface_shown(self)

        self._init_layout()

    def _init_layout(self) -> None:
        """
        初始化布局
        :return:
        """
        if self._init:
            return

        # 创建一个垂直布局
        main_layout = QVBoxLayout(self)
        scroll_area = SingleDirectionScrollArea(orient=Qt.Orientation.Vertical)
        # 暴露滚动区域，方便容器级拖拽等场景使用
        self.scroll_area = scroll_area
        main_layout.addWidget(scroll_area, stretch=0)

        content_widget = self._param_content_widget
        if content_widget is None:
            content_widget = self.get_content_widget()
        content_widget.setStyleSheet("QWidget { background-color: transparent; }")
        scroll_area.setWidget(content_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        self._init = True

    def get_content_widget(self) -> QWidget:
        """
        子界面内的内容组件 由子类实现
        :return:
        """
        pass