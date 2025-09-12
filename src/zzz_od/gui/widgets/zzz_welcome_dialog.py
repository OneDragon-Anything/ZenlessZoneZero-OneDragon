from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QSpacerItem, QSizePolicy
from qfluentwidgets import PushButton
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.welcome_dialog import WelcomeDialog


class ZWelcomeDialog(WelcomeDialog):
    """自定义欢迎对话框，继承自 WelcomeDialog"""

    def __init__(self, parent=None):
        WelcomeDialog.__init__(self, parent, title=gt('欢迎使用绝区零一条龙'))

    def _setup_buttons(self):
        """设置对话框按钮"""
        essential_setup_button = PushButton(gt('必要设置'), self)
        essential_setup_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://one-dragon.com/zzz/zh/docs/config.html")))
        essential_setup_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        essential_setup_button.adjustSize()

        doc_button = PushButton(gt('自助排障'), self)
        doc_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://docs.qq.com/doc/p/7add96a4600d363b75d2df83bb2635a7c6a969b5")))
        doc_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        doc_button.adjustSize()

        github_button = PushButton(gt('开源地址'), self)
        github_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon")))
        github_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        github_button.adjustSize()

        spacer = QSpacerItem(10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(essential_setup_button)
        button_layout.addItem(spacer)
        button_layout.addWidget(doc_button)
        button_layout.addItem(spacer)
        button_layout.addWidget(github_button)
        button_layout.addStretch(1)
        self.viewLayout.addLayout(button_layout)