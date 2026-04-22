from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import FluentIconBase, SingleDirectionScrollArea

from one_dragon_qt.widgets.base_interface import BaseInterface


class VerticalScrollInterface(BaseInterface):

    def __init__(self, content_widget: QWidget | None, object_name: str,
                 nav_text_cn: str, nav_icon: FluentIconBase | QIcon | str = '',
                 parent=None):
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

        self._param_content_widget: QWidget | None = content_widget
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

        # 创建一个垂直布局，底边距为0（由滚动内容末尾的11px空白提供视觉边距）
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = self._param_content_widget
        if content_widget is None:
            content_widget = self.get_content_widget()

        top_widget = self.get_fixed_top_widget()
        if top_widget is not None:
            top_wrapper = QWidget(self)
            top_wrapper.setStyleSheet("QWidget { background-color: transparent; }")
            top_wrapper_layout = QVBoxLayout(top_wrapper)
            top_wrapper_layout.setContentsMargins(11, 0, 11, 0)
            top_wrapper_layout.setSpacing(0)
            top_wrapper_layout.addWidget(top_widget)
            main_layout.addWidget(top_wrapper, stretch=0)

        scroll_area = SingleDirectionScrollArea(orient=Qt.Orientation.Vertical)
        scroll_area.setViewportMargins(11, 0, 11, 0)
        main_layout.addWidget(scroll_area, stretch=1)

        # 包一层容器，用底边距在滚动内容末尾提供视觉边距
        wrapper = QWidget()
        wrapper.setStyleSheet("QWidget { background-color: transparent; }")
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 11)
        wrapper_layout.setSpacing(0)
        content_widget.setStyleSheet("QWidget { background-color: transparent; }")
        wrapper_layout.addWidget(content_widget)

        scroll_area.setWidget(wrapper)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        self._init = True

    def get_content_widget(self) -> QWidget:
        """
        子界面内的内容组件 由子类实现
        :return:
        """
        raise NotImplementedError

    def get_fixed_top_widget(self) -> QWidget | None:
        """
        返回固定在滚动区域上方的顶部组件。

        子类可重写该方法以实现“顶部固定、内容滚动”的布局。
        默认不显示固定顶部区域。
        """
        return None
