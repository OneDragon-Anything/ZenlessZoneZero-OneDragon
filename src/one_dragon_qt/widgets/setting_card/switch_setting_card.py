from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtGui import Qt
from qfluentwidgets import FluentIconBase
from qfluentwidgets import SwitchButton, IndicatorPosition
from typing import Union, Optional

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class SwitchSettingCard(SettingCardBase):
    """带切换开关的设置卡片类"""

    value_changed = Signal(bool)

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str] = None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 on_text_cn: str = "开",
                 off_text_cn: str = "关",
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

        # 创建按钮并设置相关属性
        self.btn = SwitchButton(parent=self, indicatorPos=IndicatorPosition.RIGHT)
        self.btn._offText = gt(off_text_cn)
        self.btn._onText = gt(on_text_cn)
        self.btn.label.setText(self.btn._offText)
        self.btn.checkedChanged.connect(self._on_value_changed)

        self.adapter: YamlConfigAdapter = adapter

        # 将按钮添加到布局
        self.hBoxLayout.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

    def _on_value_changed(self, value: bool):
        # 更新配置适配器中的值并发出信号
        if self.adapter is not None:
            self.adapter.set_value(value)
        self.value_changed.emit(value)

    def init_with_adapter(self, adapter: YamlConfigAdapter) -> None:
        """使用配置适配器初始化值"""
        self.adapter = adapter
        self.setValue(self.adapter.get_value(), emit_signal=False)

    def setValue(self, value: bool, emit_signal: bool = True):
        """设置开关状态并更新文本"""
        if not emit_signal:
            self.btn.blockSignals(True)
        self.btn.setChecked(value)
        if not emit_signal:
            self.btn.blockSignals(False)
