from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QPushButton
from qfluentwidgets import FluentIconBase
from typing import Union, Optional

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase


class PushSettingCard(SettingCardBase):
    """带推送按钮的设置卡片类"""

    clicked = Signal()

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, text: str, content: Optional[str]=None,
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

        # 创建按钮并添加到布局中
        self.button = QPushButton(gt(text), self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        # 连接按钮点击信号到自定义的 clicked 信号
        self.button.clicked.connect(self.clicked.emit)
