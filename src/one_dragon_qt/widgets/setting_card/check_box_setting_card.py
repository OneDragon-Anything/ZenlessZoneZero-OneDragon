from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtGui import Qt
from qfluentwidgets import CheckBox
from qfluentwidgets import SettingCard, FluentIconBase
from typing import Union, Optional

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase


class CheckBoxSettingCard(SettingCardBase):

    value_changed = Signal(bool)

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str]=None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 parent=None):
        SettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size,
            margins=margins,
            parent=parent
        )

        # 初始化 CheckBox
        self.check_box = CheckBox(self)
        self.hBoxLayout.addWidget(self.check_box, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        # 连接信号
        self.check_box.checkStateChanged.connect(self._on_value_changed)

    def _on_value_changed(self, value: Qt.CheckState) -> None:
        """
        值发生改变时 往外发送信号
        :param value:
        :return:
        """
        bool_value = value == Qt.CheckState.Checked
        self.value_changed.emit(bool_value)

    def setContent(self, content: str) -> None:
        """
        更新左侧详细文本
        :param content: 文本 中文
        :return:
        """
        SettingCard.setContent(self, gt(content))

    def setValue(self, bool_value: bool) -> None:
        """
        设置值
        :param bool_value:
        :return:
        """
        self.check_box.setChecked(bool_value)
