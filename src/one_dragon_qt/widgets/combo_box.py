from typing import Any, List, Optional

from qfluentwidgets import ComboBox as qtComboBox

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import (
    subscribe_language_changed,
    unsubscribe_language_changed,
)
from one_dragon_qt.widgets.adapter_init_mixin import AdapterInitMixin
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class ComboBox(qtComboBox, AdapterInitMixin):

    def __init__(self, parent=None):
        qtComboBox.__init__(self, parent)
        AdapterInitMixin.__init__(self)
        self._items_source: list[ConfigItem] = []
        self._language_callback = self.retranslate_ui
        subscribe_language_changed(self._language_callback)
        self.destroyed.connect(self._on_destroyed)

        self.adapter: Optional[YamlConfigAdapter] = None

        self.currentIndexChanged.connect(self._on_index_changed)

    def set_items(self, items: List[ConfigItem], target_value: Any = None) -> None:
        """
        更新选项
        且尽量复用原来的选项
        """
        self._items_source = list(items)
        self.blockSignals(True)

        old_data = self.currentData() if target_value is None else target_value
        old_len, new_len = len(self.items), len(items)
        new_idx = -1

        # 更新已有选项和查找当前选项索引
        for i in range(min(old_len, new_len)):
            self.setItemText(i, items[i].ui_text)
            self.setItemData(i, items[i].value)
            if items[i].value == old_data:
                new_idx = i

        # 移除多余的选项
        for _ in range(new_len, old_len):
            self.removeItem(new_len)

        # 添加新选项
        for i in range(old_len, new_len):
            item = items[i]
            self.addItem(item.ui_text, userData=item.value)
            if item.value == old_data:
                new_idx = i

        self.setCurrentIndex(new_idx)
        self.blockSignals(False)

    def _on_destroyed(self, _object=None) -> None:
        """Unsubscribe the combo box after Qt destroys it."""
        unsubscribe_language_changed(self._language_callback)

    def retranslate_ui(self, _language: str | None = None) -> None:
        """Refresh combo-box labels after the application language changes."""
        current_value = self.currentData()
        self.blockSignals(True)
        for index, item in enumerate(self._items_source):
            self.setItemText(index, item.ui_text)
        self.blockSignals(False)
        if current_value is not None:
            self.setCurrentIndex(self.findData(current_value))

    def init_with_value(self, target_value: Any = None) -> None:
        """
        根据目标值初始化 不抛出事件
        :param target_value:
        :return:
        """
        self.blockSignals(True)
        self.setCurrentIndex(self.findData(target_value))
        self.blockSignals(False)

    def _on_index_changed(self, index: int) -> None:
        """索引变化时发射信号"""
        val = self.itemData(index)

        if self.adapter is not None:
            self.adapter.set_value(val)

    def setValue(self, value: object, emit_signal: bool = True) -> None:
        """设置下拉框的值。"""
        if not emit_signal:
            self.blockSignals(True)

        if value is None:
            self.last_index = -1
            self.setCurrentIndex(-1)
        else:
            for idx in range(self.count()):
                if self.itemData(idx) == value:
                    self.setCurrentIndex(idx)
                    break

        if not emit_signal:
            self.blockSignals(False)

    def getValue(self) -> object:
        """获取下拉框的值。"""
        return self.itemData(self.currentIndex())
