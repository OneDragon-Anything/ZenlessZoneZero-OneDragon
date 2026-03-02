"""双下拉框设置卡片 —— 修饰键 + 按钮组合。

用于后台模式手柄动作键配置，一张卡片包含两个下拉框（修饰键、按钮），
组合值以 'modifier+button' 格式存储，如 'xbox_lb+xbox_a' 表示 LB+A。
"""

from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIconBase

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.controller.pc_button.gamepad_combo import (
    compose_gamepad_key,
    decompose_gamepad_key,
)
from one_dragon_qt.utils.layout_utils import IconSize, Margins
from one_dragon_qt.widgets.adapter_init_mixin import AdapterInitMixin
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase


class DualComboBoxSettingCard(SettingCardBase, AdapterInitMixin):
    """包含修饰键 + 按钮两个下拉框的设置卡片。

    存储值格式: 'modifier+button' (如 'xbox_lb+xbox_a') 或 'button' (如 'xbox_a')。
    """

    value_changed = Signal(str)

    def __init__(
        self,
        icon: str | QIcon | FluentIconBase,
        title: str,
        modifier_enum: type[Enum],
        button_enum: type[Enum],
        content: str | None = None,
        icon_size: IconSize | None = None,
        margins: Margins | None = None,
        parent=None,
    ):
        if icon_size is None:
            icon_size = IconSize(16, 16)
        if margins is None:
            margins = Margins(16, 16, 0, 16)
        SettingCardBase.__init__(
            self, icon=icon, title=title, content=content,
            icon_size=icon_size, margins=margins, parent=parent,
        )
        AdapterInitMixin.__init__(self)

        # ── 修饰键下拉框 ──
        self.modifier_combo = ComboBox(self)
        self.modifier_combo.addItem('无', userData='')
        for item in modifier_enum:
            ci: ConfigItem = item.value
            self.modifier_combo.addItem(ci.ui_text, userData=ci.value)
        self.modifier_combo.setCurrentIndex(0)

        # ── 按钮下拉框 ──
        self.button_combo = ComboBox(self)
        for item in button_enum:
            ci: ConfigItem = item.value
            self.button_combo.addItem(ci.ui_text, userData=ci.value)
        self.button_combo.setCurrentIndex(0)

        # ── 布局 ──
        self.hBoxLayout.addWidget(self.modifier_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.button_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        # ── 信号 ──
        self._updating = False
        self.modifier_combo.currentIndexChanged.connect(self._on_combo_changed)
        self.button_combo.currentIndexChanged.connect(self._on_combo_changed)

    # ── 内部方法 ──

    def _on_combo_changed(self, _index: int) -> None:
        """任一下拉框变化时，组合值并同步 adapter。"""
        if self._updating:
            return
        modifier = self.modifier_combo.currentData() or ''
        button = self.button_combo.currentData() or ''
        value = compose_gamepad_key(modifier, button)

        if self.adapter is not None:
            self.adapter.set_value(value)

        self.value_changed.emit(value)

    # ── AdapterInitMixin 接口 ──

    def setValue(self, value: object, emit_signal: bool = True) -> None:
        """从存储值设置两个下拉框。"""
        self._updating = True
        modifier_val, button_val = decompose_gamepad_key(str(value) if value else '')

        for i in range(self.modifier_combo.count()):
            if self.modifier_combo.itemData(i) == modifier_val:
                self.modifier_combo.setCurrentIndex(i)
                break

        for i in range(self.button_combo.count()):
            if self.button_combo.itemData(i) == button_val:
                self.button_combo.setCurrentIndex(i)
                break

        self._updating = False

        if emit_signal:
            combined = compose_gamepad_key(modifier_val, button_val)
            self.value_changed.emit(combined)

    def getValue(self) -> str:
        """获取当前组合值。"""
        modifier = self.modifier_combo.currentData() or ''
        button = self.button_combo.currentData() or ''
        return compose_gamepad_key(modifier, button)
