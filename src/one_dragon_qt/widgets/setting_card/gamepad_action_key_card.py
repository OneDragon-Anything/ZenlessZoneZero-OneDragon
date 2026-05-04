from enum import Enum

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIconBase

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.utils.layout_utils import IconSize, Margins
from one_dragon_qt.widgets.adapter_init_mixin import AdapterInitMixin
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)


class GamepadActionKeyCard(MultiPushSettingCard, AdapterInitMixin):
    """手柄动作键卡片：修饰键 + 按钮。

    用于后台模式手柄动作键配置，一张卡片包含两个下拉框（修饰键、按钮），
    组合值以 list[str] 格式存储，如 ['xbox_lb', 'xbox_a'] 表示 LB+A。
    """

    value_changed = Signal(list)

    def __init__(
        self,
        icon: str | QIcon | FluentIconBase,
        title: str,
        modifier_enum: type[Enum],
        button_enum: type[Enum],
        content: str | None = None,
        icon_size: IconSize = IconSize(16, 16),
        margins: Margins = Margins(16, 16, 0, 16),
        parent: QWidget = None,
    ) -> None:
        self.modifier_combo = ComboBox()
        self.modifier_combo.addItem('无', userData='')
        for item in modifier_enum:
            ci: ConfigItem = item.value
            self.modifier_combo.addItem(ci.ui_text, userData=ci.value)
        self.modifier_combo.setCurrentIndex(0)

        self.button_combo = ComboBox()
        for item in button_enum:
            ci: ConfigItem = item.value
            self.button_combo.addItem(ci.ui_text, userData=ci.value)
        self.button_combo.setCurrentIndex(0)

        MultiPushSettingCard.__init__(
            self, icon=icon, title=title, content=content,
            icon_size=icon_size, margins=margins,
            btn_list=[self.modifier_combo, self.button_combo],
            parent=parent,
        )
        AdapterInitMixin.__init__(self)

        self._updating = False
        self.modifier_combo.currentIndexChanged.connect(self._on_combo_changed)
        self.button_combo.currentIndexChanged.connect(self._on_combo_changed)

    def _on_combo_changed(self, _index: int) -> None:
        """任一下拉框变化时，组合值并同步 adapter。"""
        if self._updating:
            return
        value = self.getValue()

        if self.adapter is not None:
            self.adapter.set_value(value)

        self.value_changed.emit(value)

    def setValue(self, value: object, emit_signal: bool = True) -> None:
        """从存储值设置两个下拉框。"""
        self._updating = True
        keys = value if isinstance(value, list) else []
        modifier_val = keys[0] if len(keys) >= 2 else ''
        button_val = keys[-1] if keys else ''

        idx = self.modifier_combo.findData(modifier_val)
        self.modifier_combo.setCurrentIndex(idx if idx >= 0 else 0)

        idx = self.button_combo.findData(button_val)
        self.button_combo.setCurrentIndex(idx if idx >= 0 else 0)

        self._updating = False

        if emit_signal:
            self.value_changed.emit(self.getValue())

    def getValue(self) -> list[str]:
        """获取当前组合值。"""
        modifier = self.modifier_combo.currentData() or ''
        button = self.button_combo.currentData() or ''
        if modifier:
            return [modifier, button]
        return [button]
