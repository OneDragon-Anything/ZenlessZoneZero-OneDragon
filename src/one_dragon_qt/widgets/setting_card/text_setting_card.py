from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLineEdit
from qfluentwidgets import FluentIconBase, FluentIcon
from qfluentwidgets import LineEdit, ToolButton
from typing import Union, Optional

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class TextSettingCard(SettingCardBase):
    """带文本输入框的设置卡片类"""

    title: str

    value_changed = Signal(str)

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str] = None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 input_placeholder: Optional[str] = None,
                 input_max_width: int = 300,
                 adapter: Optional[YamlConfigAdapter] = None,
                 is_password: bool = False,  # 控制是否为密码模式
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

        # 创建输入框控件
        self.line_edit = LineEdit(self)
        self.line_edit.setMaximumWidth(input_max_width)
        self.line_edit.setPlaceholderText(gt(input_placeholder))
        self.line_edit.setClearButtonEnabled(True)

        self.adapter: YamlConfigAdapter = adapter

        # 设置密码模式
        if is_password:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.line_edit.setMaximumWidth(input_max_width - 45)

            # 添加切换显示/隐藏明文的按钮
            self.toggle_button = ToolButton(FluentIcon.HIDE)
            self.toggle_button.setCheckable(True)
            self.toggle_button.setFixedSize(40, 33)  # 固定按钮大小
            self.toggle_button.clicked.connect(self._toggle_password_visibility)

            # 创建一个水平布局，将输入框和按钮放在一起
            self.input_layout = QHBoxLayout()
            self.input_layout.setContentsMargins(0, 0, 0, 0)  # 去掉内边距
            self.input_layout.addWidget(self.line_edit)  # 左侧为输入框
            self.input_layout.addSpacing(5)  # 添加空隙
            self.input_layout.addWidget(self.toggle_button)  # 右侧为按钮

            # 将水平布局添加到卡片的主布局中
            self.hBoxLayout.addLayout(self.input_layout, 1)
        else:
            # 如果不是密码模式，仅添加输入框
            self.hBoxLayout.addWidget(self.line_edit, 1)

        # 添加额外的间距（如果需要）
        self.hBoxLayout.addSpacing(16)

        # 绑定输入框内容变化信号
        self.line_edit.editingFinished.connect(self._on_text_changed)

    def _toggle_password_visibility(self):
        """切换密码显示模式"""
        if self.toggle_button.isChecked():
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Normal)  # 显示明文
            self.toggle_button.setIcon(FluentIcon.VIEW)
        else:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)  # 隐藏明文
            self.toggle_button.setIcon(FluentIcon.HIDE)

    def _on_text_changed(self) -> None:
        """处理文本更改事件"""
        val = self.line_edit.text()

        if self.adapter is not None:
            self.adapter.set_value(val)

        self.value_changed.emit(val)

    def init_with_adapter(self, adapter: Optional[YamlConfigAdapter]) -> None:
        """使用配置适配器初始化值"""
        self.adapter = adapter

        if self.adapter is None:
            self.setValue("", emit_signal=False)
        else:
            self.setValue(self.adapter.get_value(), emit_signal=False)

    def setValue(self, value: str, emit_signal: bool = True) -> None:
        """设置输入框的值"""
        if not emit_signal:
            self.line_edit.blockSignals(True)
        self.line_edit.setText(value)
        if not emit_signal:
            self.line_edit.blockSignals(False)


