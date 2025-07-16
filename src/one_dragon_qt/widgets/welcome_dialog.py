from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QSpacerItem, QSizePolicy
from qfluentwidgets import MessageBoxBase, PushButton, SubtitleLabel, DisplayLabel

class WelcomeDialog(MessageBoxBase):
    """首次运行时显示的欢迎对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.cancelButton.hide()
        self.yesButton.setText("确定(5s)")
        self.yesButton.setEnabled(False)
        
        self.titleLabel = SubtitleLabel("欢迎使用绝区零一条龙")
        self.viewLayout.addWidget(self.titleLabel)

        content_label = DisplayLabel(self)
        content_label.setText("本软件完全<font color='red'>开源 免费</font><br>不要在<font color='red'>第三方渠道</font>购买<br>谨防<font color='red'>诈骗 盗号</font>")

        self.viewLayout.addWidget(content_label)
        self._setup_buttons()
        self._start_countdown()
    
    def _setup_buttons(self):
        """设置对话框按钮"""
        quick_start_button = PushButton("快速开始", self)
        quick_start_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://onedragon-anything.github.io/zzz/zh/quickstart.html")))
        quick_start_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        quick_start_button.adjustSize()

        doc_button = PushButton("自助排障", self)
        doc_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.kdocs.cn/l/cbSJUUNotJ3Z")))
        doc_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        doc_button.adjustSize()

        github_button = PushButton("开源地址", self)
        github_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/DoctorReid/ZenlessZoneZero-OneDragon")))
        github_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        github_button.adjustSize()

        spacer = QSpacerItem(10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(quick_start_button)
        button_layout.addItem(spacer)
        button_layout.addWidget(doc_button)
        button_layout.addItem(spacer)
        button_layout.addWidget(github_button)
        button_layout.addStretch(1)
        self.viewLayout.addLayout(button_layout)
    
    def _start_countdown(self):
        """启动倒计时"""
        self.countdown_value = 5
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)  # 1秒
        self.countdown_timer.timeout.connect(self._update_countdown)
        self.countdown_timer.start()
    
    def _update_countdown(self):
        """更新确认按钮上的倒计时"""
        self.countdown_value -= 1
        if self.countdown_value > 0:
            self.yesButton.setText(f"确定({self.countdown_value}s)")
        else:
            self.yesButton.setText("确定")
            self.yesButton.setEnabled(True)
            self.countdown_timer.stop()
