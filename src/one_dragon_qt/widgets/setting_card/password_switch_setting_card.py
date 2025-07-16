import hashlib

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLineEdit
from qfluentwidgets import Dialog, FluentIcon, FluentIconBase, IndicatorPosition, LineEdit, SwitchButton, ToolButton
from typing import Union, Optional

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class PasswordSwitchSettingCard(SettingCardBase):
    """带密码的切换开关的设置卡片类"""

    value_changed = Signal(bool)

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str] = None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 on_text_cn: str = "开",
                 off_text_cn: str = "关",
                 adapter: Optional[YamlConfigAdapter] = None,
                 extra_btn: Optional[QAbstractButton] = None,
                 parent=None,
                 password_hint: str = "请输入密码",
                 password_hash: str = "",
                 dialog_title: str = "提示",
                 dialog_content: str = "密码错误，请重新输入",
                 dialog_button_text: str = "确定"):

        SettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size,
            margins=margins,
            parent=parent
        )

        # 初始化属性
        self.password_hash = password_hash
        self.password_hint = gt(password_hint)
        self.dialog_title = gt(dialog_title)
        self.dialog_content = gt(dialog_content)
        self.dialog_button_text = gt(dialog_button_text)

        # 创建按钮并设置相关属性
        self.btn = SwitchButton(parent=self, indicatorPos=IndicatorPosition.RIGHT)
        self.btn._offText = gt(off_text_cn)
        self.btn._onText = gt(on_text_cn)
        self.btn.label.setText(self.btn._offText)
        self.btn.checkedChanged.connect(self._on_value_changed)

        self.adapter: YamlConfigAdapter = adapter

        # 添加密码输入框
        self.password = LineEdit()
        self.password.setPlaceholderText(self.password_hint)
        self.password.setMinimumWidth(210)
        self.password.setClearButtonEnabled(True)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setMaximumWidth(self.password.maximumWidth() - 45)

        # 添加切换显示/隐藏明文的按钮
        self.toggle_button = ToolButton(FluentIcon.HIDE)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setFixedSize(40, 33)  # 固定按钮大小
        self.toggle_button.clicked.connect(self._toggle_password_visibility)

        # 创建一个水平布局，将输入框和按钮放在一起
        self.password_layout = QHBoxLayout()
        self.password_layout.setContentsMargins(0, 0, 0, 0)  # 去掉内边距
        self.password_layout.addWidget(self.password)  # 左侧为输入框
        self.password_layout.addSpacing(5)  # 添加空隙
        self.password_layout.addWidget(self.toggle_button)  # 右侧为按钮

        # 将按钮添加到布局
        self.extra_btn = extra_btn
        if self.extra_btn is not None:
            self.hBoxLayout.addWidget(self.extra_btn, 0, Qt.AlignmentFlag.AlignRight)
            self.hBoxLayout.addSpacing(16)
        self.hBoxLayout.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.hBoxLayout.insertLayout(4, self.password_layout, 0)

    def _set_extra_button_enabled(self, value: bool):
        if self.extra_btn is not None:
            self.extra_btn.setEnabled(value)

    def _toggle_password_visibility(self):
        """切换密码显示模式"""
        if self.toggle_button.isChecked():
            self.password.setEchoMode(QLineEdit.EchoMode.Normal)  # 显示明文
            self.toggle_button.setIcon(FluentIcon.VIEW)
        else:
            self.password.setEchoMode(QLineEdit.EchoMode.Password)  # 隐藏明文
            self.toggle_button.setIcon(FluentIcon.HIDE)

    def _on_value_changed(self, value: bool):
        # 更新配置适配器中的值并发出信号
        if value:
            if hashlib.sha256(self.password.text().encode()).hexdigest() != self.password_hash:
                dialog = Dialog(self.dialog_title, self.dialog_content, self)
                dialog.setTitleBarVisible(False)
                dialog.yesButton.setText(self.dialog_button_text)
                dialog.cancelButton.hide()
                dialog.exec()

                self.setValue(False, emit_signal=False)
                self._set_extra_button_enabled(False)
                value = False
            else:
                self._set_extra_button_enabled(True)
        else:
            self._set_extra_button_enabled(False)
        if self.adapter is not None:
            self.adapter.set_value(value)
        self.value_changed.emit(value)

    def init_with_adapter(self, adapter: YamlConfigAdapter) -> None:
        """使用配置适配器初始化值"""
        self.adapter = adapter
        value = self.adapter.get_value()
        self.setValue(value, emit_signal=False)
        self._set_extra_button_enabled(value)

    def setValue(self, value: bool, emit_signal: bool = True):
        """设置开关状态并更新文本"""
        if not emit_signal:
            self.btn.blockSignals(True)
        self.btn.setChecked(value)
        if not emit_signal:
            self.btn.blockSignals(False)
