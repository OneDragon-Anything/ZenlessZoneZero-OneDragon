from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIconBase, InfoBarIcon, InfoBarPosition, InfoBar
from typing import Union

from one_dragon.utils.i18_utils import gt

try:
    from zzz_od.telemetry.auto_telemetry import TelemetryInterfaceMixin, auto_telemetry_method
except ImportError:
    class TelemetryInterfaceMixin:
        def track_interface_shown(self): pass
        def track_interface_hidden(self): pass

    def auto_telemetry_method(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

class BaseInterface(QWidget, TelemetryInterfaceMixin):

    def __init__(self,
                 object_name: str,
                 nav_text_cn: str,
                 nav_icon: Union[FluentIconBase, QIcon, str] = None,
                 parent=None):
        """
        包装一个子页面需要有的内容
        :param object_name: 导航用的唯一键
        :param nav_text_cn: 出现在导航上的中文
        :param nav_icon: 出现在导航上的图标
        """
        QWidget.__init__(self, parent=parent)
        self.nav_text: str = gt(nav_text_cn)
        self.nav_icon: Union[FluentIconBase, QIcon, str] = nav_icon
        self.setObjectName(object_name)

    @auto_telemetry_method("interface_shown")
    def on_interface_shown(self) -> None:
        """
        子界面显示时 进行初始化
        :return:
        """
        self.track_interface_shown()

    @auto_telemetry_method("interface_hidden")
    def on_interface_hidden(self) -> None:
        """
        子界面隐藏时的回调
        :return:
        """
        self.track_interface_hidden()

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
            title=title,
            content=content,
            orient=orient,
            isClosable=is_closable,
            duration=duration,
            position=position,
            parent=self if parent is None else parent,
        )
