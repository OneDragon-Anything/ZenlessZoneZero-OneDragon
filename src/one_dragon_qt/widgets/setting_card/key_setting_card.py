from PySide6.QtCore import QObject
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtGui import Qt
from qfluentwidgets import PushButton
from qfluentwidgets import SettingCard, FluentIconBase
from typing import Union, Optional

from one_dragon.base.controller.pc_button.pc_button_listener import PcButtonListener
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class KeyEventWorker(QObject):

    key_pressed = Signal(str)

    def on_key_press(self, key: str) -> None:
        """
        按键后触发 发送信号
        :param key:
        :return:
        """
        self.key_pressed.emit(key)


class KeySettingCard(SettingCardBase):

    value_changed = Signal(str)

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str]=None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 adapter: Optional[YamlConfigAdapter] = None,
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

        # 初始化 PushButton
        self.value: str = ''
        self.btn = PushButton(text='', parent=self)
        self.btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn.clicked.connect(self._on_btn_clicked)

        self.adapter: YamlConfigAdapter = adapter

        # 初始化监听器和键盘事件工作者
        self.button_listener = None  # 按键监听
        self.key_worker = KeyEventWorker()
        self.key_worker.key_pressed.connect(self._on_key_signal)

        # 布局处理
        self.hBoxLayout.addWidget(self.btn, 1, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def _on_btn_clicked(self) -> None:
        """
        点击按钮后 开始监听按键事件
        :return:
        """
        if self.button_listener is None:
            self.button_listener = PcButtonListener(
                self._on_key_press, listen_keyboard=True, listen_mouse=True
            )
            self.btn.setText(gt('请按键'))
            self.button_listener.start()
        else:
            self._stop_listener()
            self.btn.setText(self.value.upper())

    def _on_key_press(self, key):
        """
        按键时触发
        :param key:
        :return:
        """
        self._stop_listener()
        self.key_worker.on_key_press(key)

    def _on_key_signal(self, key: str) -> None:
        """
        :param key:
        :return:
        """
        self.setValue(key)

        if self.adapter is not None:
            self.adapter.set_value(key)

    def init_with_adapter(self, adapter: YamlConfigAdapter) -> None:
        """
        初始化值
        """
        self.adapter = adapter
        self.setValue(self.adapter.get_value(), emit_signal=False)

    def setContent(self, content: str) -> None:
        """
        更新左侧详细文本
        :param content: 文本 中文
        :return:
        """
        SettingCard.setContent(self, gt(content))

    def setValue(self, value: str, emit_signal: bool = True) -> None:
        """
        设置值
        :param value:
        :param emit_signal: 是否发送信号
        :return:
        """
        self.value = value
        self.btn.setText(value.upper())
        if emit_signal:
            self.value_changed.emit(value)

    def _stop_listener(self) -> None:
        """
        停止键盘鼠标的监听
        :return:
        """
        if self.button_listener is not None:
            self.button_listener.stop()
            self.button_listener = None
