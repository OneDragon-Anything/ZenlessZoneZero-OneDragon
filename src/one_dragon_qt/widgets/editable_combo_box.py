from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter

from qfluentwidgets import EditableComboBox as qtEditableComboBox
from one_dragon.base.config.config_item import ConfigItem
from typing import List, Any


class EditableComboBox(qtEditableComboBox):

    def __init__(self, parent=None):
        qtEditableComboBox.__init__(self, parent)

    def _onReturnPressed(self):
        """
        子类重写
        不向列表添加新选项
        """
        if not self.text():
            return

        index = self.findText(self.text())
        if index >= 0 and index != self.currentIndex():
            self._currentIndex = index
            self.currentIndexChanged.emit(index)

    def set_items(self, items: List[ConfigItem], target_value: Any = None) -> None:
        """
        更新选项
        且尽量复用原来的选项
        """
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
        for i in range(new_len, old_len):
            self.removeItem(new_len)

        # 添加新选项
        for i in range(old_len, new_len):
            item = items[i]
            self.addItem(item.ui_text, userData=item.value)
            if item.value == old_data:
                new_idx = i

        self.setCurrentIndex(new_idx)
        self.set_completer_options(items)
        self.blockSignals(False)

    def init_with_value(self, target_value: Any = None) -> None:
        """
        根据目标值初始化 不抛出事件
        :param target_value:
        :return:
        """
        self.blockSignals(True)
        self.setCurrentIndex(self.findData(target_value))
        self.blockSignals(False)

    def set_completer_options(self, options_list: List[ConfigItem]) -> None:
        """初始化自动补全器"""
        completion_strings = [item.ui_text for item in options_list]
        completer = QCompleter(completion_strings)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)  # 设置大小写不敏感
        completer.setFilterMode(Qt.MatchFlag.MatchContains)  # 设置匹配模式为包含
        self.setCompleter(completer)