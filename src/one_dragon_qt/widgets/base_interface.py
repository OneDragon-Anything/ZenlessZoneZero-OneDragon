from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QWidget,
)
from qfluentwidgets import FluentIconBase, InfoBar, InfoBarIcon, InfoBarPosition

from one_dragon.utils.i18_utils import get_source_msgid, gt


class BaseInterface(QWidget):

    def __init__(self,
                 object_name: str,
                 nav_text_cn: str,
                 nav_icon: FluentIconBase | QIcon | str,
                 parent=None):
        """
        包装一个子页面需要有的内容
        :param object_name: 导航用的唯一键
        :param nav_text_cn: 出现在导航上的中文
        :param nav_icon: 出现在导航上的图标
        """
        QWidget.__init__(self, parent=parent)
        self.nav_text_cn: str = nav_text_cn
        self.nav_text: str = gt(nav_text_cn)
        self.nav_icon: FluentIconBase | QIcon | str = nav_icon
        self.setObjectName(object_name)

    def retranslate_ui(self) -> None:
        """Refresh the navigation label after a language change."""
        self.nav_text = gt(self.nav_text_cn)
        for child in self.findChildren(QWidget):
            retranslate = getattr(child, 'retranslate_ui', None)
            if callable(retranslate):
                retranslate()
            self._retranslate_widget_text(child)
            if child.__class__.__name__ == 'SettingCardGroup':
                title_label = getattr(child, 'titleLabel', None)
                if title_label is not None:
                    source = get_source_msgid(title_label.text())
                    if source is not None:
                        title_label.setText(gt(source))

    @staticmethod
    def _retranslate_widget_text(widget: QWidget) -> None:
        """Translate standard Qt text properties for legacy UI widgets."""
        if isinstance(widget, QLabel):
            source = get_source_msgid(widget.text())
            if source is not None:
                widget.setText(gt(source))
        if isinstance(widget, QAbstractButton):
            source = get_source_msgid(widget.text())
            if source is not None:
                widget.setText(gt(source))
        if isinstance(widget, QLineEdit):
            source = get_source_msgid(widget.placeholderText())
            if source is not None:
                widget.setPlaceholderText(gt(source))
        if isinstance(widget, QPlainTextEdit):
            source = get_source_msgid(widget.placeholderText())
            if source is not None:
                widget.setPlaceholderText(gt(source))
        if isinstance(widget, QComboBox):
            for index in range(widget.count()):
                source = get_source_msgid(widget.itemText(index))
                if source is not None:
                    widget.setItemText(index, gt(source))
        if isinstance(widget, QTableWidget):
            for index in range(widget.columnCount()):
                header = widget.horizontalHeaderItem(index)
                if header is not None:
                    source = get_source_msgid(header.text())
                    if source is not None:
                        header.setText(gt(source))
            for index in range(widget.rowCount()):
                header = widget.verticalHeaderItem(index)
                if header is not None:
                    source = get_source_msgid(header.text())
                    if source is not None:
                        header.setText(gt(source))
        source = get_source_msgid(widget.toolTip())
        if source is not None:
            widget.setToolTip(gt(source))

    def on_interface_leave(self) -> None:
        """
        视觉切换前调用，用于恢复 margin/标题栏等必须同步的视觉状态
        :return:
        """
        pass

    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        pass

    def on_interface_hidden(self) -> None:
        """
        子界面隐藏时的回调
        :return:
        """
        pass

    def show_info_bar(
            self,
            title: str,
            content: str,
            icon: InfoBarIcon = InfoBarIcon.INFORMATION,
            orient: Qt.Orientation = Qt.Orientation.Horizontal,
            is_closable: bool = True,
            duration: int = 1000,
            position: InfoBarPosition = InfoBarPosition.TOP_RIGHT,
            parent=None,
    ):
        """
        通用的提示

        Args:
            title: 标题
            content: 内容
            icon: 图标
            orient: 提示显示的方向
            is_closable: 是否可关闭
            duration: 持续时间 ms
            position: 提示显示的位置
            parent: 父控件
        """
        return InfoBar.new(
            icon=icon,
            title=gt(title),
            content=gt(content),
            orient=orient,
            isClosable=is_closable,
            duration=duration,
            position=position,
            parent=self if parent is None else parent,
        )
