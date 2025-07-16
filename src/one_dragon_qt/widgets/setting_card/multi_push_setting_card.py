from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QAbstractButton, QVBoxLayout, QHBoxLayout
from qfluentwidgets import FluentIconBase
from typing import List
from typing import Union, Optional

from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase


class MultiPushSettingCard(SettingCardBase):
    """带多个按钮的设置卡片类"""


    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str]=None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 btn_list: List[QAbstractButton] = None,
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

        # 初始化按钮布局
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(16)
        self.btn_layout.addStretch(1)
        for btn in btn_list:
            self.btn_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.btn_layout.addSpacing(16)

        # 将按钮布局添加到卡片的主布局中
        self.hBoxLayout.addLayout(self.btn_layout, 1)


class MultiLineSettingCard(SettingCardBase):
    """带多行按钮的设置卡片类"""

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str]=None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 line_list: List[List[QAbstractButton]] = None,
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

        # 初始化纵向布局
        v_layout = QVBoxLayout()
        v_layout.setSpacing(5)
        self.hBoxLayout.addLayout(v_layout)

        # 创建每一行的按钮布局
        for line in line_list:
            h_layout = QHBoxLayout()
            h_layout.setSpacing(16)
            v_layout.addLayout(h_layout)
            h_layout.addStretch(1)
            for btn in line:
                h_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)
            h_layout.addSpacing(16)

        # 根据按钮行数调整卡片的高度
        self.setFixedHeight(60 + (len(line_list) - 1) * 30)
