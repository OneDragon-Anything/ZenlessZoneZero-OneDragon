from collections.abc import Iterable
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from qfluentwidgets import CaptionLabel, FluentIconBase

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.utils.layout_utils import IconSize, Margins
from one_dragon_qt.widgets.setting_card.editable_combo_box_setting_card import (
    EditableComboBoxSettingCard,
)


class ValueDisplayEditableComboBoxSettingCard(EditableComboBoxSettingCard):
    """可输入真实值，并在右侧显示匹配选项外显名的下拉设置卡片。"""

    def __init__(
            self,
            icon: str | QIcon | FluentIconBase,
            title: str,
            content: str = '',
            icon_size: IconSize = IconSize(16, 16),
            margins: Margins = Margins(16, 16, 0, 16),
            options_enum: Iterable[Enum] | None = None,
            options_list: list[ConfigItem] | None = None,
            input_placeholder: str | None = None,
            tooltip: str | None = None,
            display_padding: int = 8,
            minimum_combo_width: int = 360,
            parent=None,
    ):
        self._fixed_content = content
        self._display_padding = display_padding
        self._minimum_combo_width = minimum_combo_width
        EditableComboBoxSettingCard.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size,
            margins=margins,
            options_enum=options_enum,
            options_list=options_list,
            input_placeholder=input_placeholder,
            tooltip=tooltip,
            parent=parent,
        )

        self.display_label = CaptionLabel('', self.combo_box)
        self.display_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.display_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self.display_label.hide()

        drop_button_index = self.combo_box.hBoxLayout.indexOf(self.combo_box.dropButton)
        self.combo_box.hBoxLayout.insertWidget(
            drop_button_index,
            self.display_label,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

        self.combo_box.activated.connect(self._on_activated)
        self.combo_box.currentTextChanged.connect(self._on_text_changed)

        self._update_combo_box_minimum_width()
        self._apply_value(self.combo_box.itemData(self.combo_box.currentIndex()))

    def _on_index_changed(self, index: int) -> None:
        """索引变化时使用真实值填充输入框，并更新外显名。"""
        val = self.combo_box.itemData(index)
        self._apply_value(val)

        if index == self.last_index:
            return

        self.last_index = index
        self._update_desc()

        if self.adapter is not None:
            self.adapter.set_value(val)

        self.value_changed.emit(index, val)

    def _update_desc(self) -> None:
        """保持卡片说明固定，不用选项 desc 覆盖。"""
        self.setContent(self._fixed_content)

    def _on_activated(self, index: int) -> None:
        """重复点选当前项时，也恢复输入框里的真实值。"""
        self._apply_value(self.combo_box.itemData(index))

    def _on_text_changed(self, text: str) -> None:
        self._sync_display_name(self._normalize_value(text))

    def set_options_by_list(self, options: list[ConfigItem]) -> None:
        super().set_options_by_list(options)
        if hasattr(self, 'display_label'):
            self._update_combo_box_minimum_width()
        if hasattr(self, 'display_label'):
            self._sync_display_name(self.getValue())

    def setValue(self, value: object, emit_signal: bool = True) -> None:
        if not emit_signal:
            self.combo_box.blockSignals(True)

        text = '' if value is None else str(value)
        matched_idx = self.combo_box.findData(value)
        if matched_idx >= 0:
            self.last_index = matched_idx
            self.combo_box.setCurrentIndex(matched_idx)
        else:
            self.last_index = -1
            self.combo_box.setCurrentIndex(-1)
        self.combo_box.setText(text)

        if not emit_signal:
            self.combo_box.blockSignals(False)
        self._sync_display_name(text)
        self._update_desc()

    def getValue(self) -> object:
        return self._normalize_value(self.combo_box.text().strip())

    def _apply_value(self, value: object) -> None:
        text = '' if value is None else str(value)
        if self.combo_box.text() != text:
            self.combo_box.setText(text)
        self._sync_display_name(text)
        self._update_desc()

    def _sync_display_name(self, value: object) -> None:
        if not hasattr(self, 'display_label'):
            return

        display = ''
        for item in self._opts_list:
            if item.value == value:
                display = item.ui_text
                break
        self.display_label.setText(display)
        self.display_label.setToolTip(display)
        self.display_label.setVisible(bool(display))
        self._update_combo_box_text_margins(display)
        self._ensure_current_value_visible()

    def _update_combo_box_text_margins(self, display: str) -> None:
        display_width = (
            self.display_label.fontMetrics().horizontalAdvance(display)
            + self._display_padding
            if display else 0
        )
        self.display_label.setFixedWidth(display_width)
        right = 29 + (display_width + 6 if display else 0)
        margins = self.combo_box.textMargins()
        self.combo_box.setTextMargins(
            margins.left(), margins.top(), right, margins.bottom()
        )

    def _update_combo_box_minimum_width(self) -> None:
        max_width = self._minimum_combo_width
        metrics = self.combo_box.fontMetrics()
        for item in self._opts_list:
            value_width = metrics.horizontalAdvance(str(item.value))
            display_width = (
                self.display_label.fontMetrics().horizontalAdvance(item.ui_text)
                + self._display_padding
            )
            max_width = max(max_width, value_width + display_width + 48)
        self.combo_box.setMinimumWidth(max_width)

    def _ensure_current_value_visible(self) -> None:
        margins = self.combo_box.textMargins()
        value_width = self.combo_box.fontMetrics().horizontalAdvance(
            self.combo_box.text()
        )
        required_width = value_width + margins.left() + margins.right() + 24
        self.combo_box.setMinimumWidth(
            max(self.combo_box.minimumWidth(), required_width)
        )

    def _normalize_value(self, text: str) -> str:
        for item in self._opts_list:
            if item.ui_text == text:
                return str(item.value)
        return text
