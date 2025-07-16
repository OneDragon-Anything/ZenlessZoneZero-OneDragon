from PySide6.QtCore import QTimer
from qfluentwidgets import MessageBoxBase, DisplayLabel, LargeTitleLabel, SubtitleLabel
from one_dragon.utils.i18_utils import gt, get_default_lang

class WelcomeDialog(MessageBoxBase):
    """首次运行时显示的欢迎对话框"""

    def __init__(self, parent=None, title="欢迎使用一条龙"):
        super().__init__(parent)

        self.cancelButton.hide()
        self.yesButton.setText(f"{gt('确定')} (5s)")
        self.yesButton.setEnabled(False)

        self.titleLabel = SubtitleLabel(gt(title))
        self.viewLayout.addWidget(self.titleLabel)

        if get_default_lang() == 'zh':
            content_label = DisplayLabel(self)
            content_label.setText("本软件完全<font color='red'>开源 免费</font><br>\n不要在<font color='red'>第三方渠道</font>购买<br>\n谨防<font color='red'>诈骗 盗号</font>")
        else:
            content_label = LargeTitleLabel(self)
            content_label.setText("This software is completely <font color='red'>Open Source and Free</font><br>\nDo not purchase from <font color='red'>Third-party Channels</font><br>\nBeware of <font color='red'>Scams and Account Theft</font>")
        self.viewLayout.addWidget(content_label)

        self._setup_buttons()
        self._start_countdown()

    def _setup_buttons(self):
        """设置按钮布局 由子类实现"""
        pass

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
            self.yesButton.setText(f"{gt('确定')} ({self.countdown_value}s)")
        else:
            self.yesButton.setText(gt('确定'))
            self.yesButton.setEnabled(True)
            self.countdown_timer.stop()
