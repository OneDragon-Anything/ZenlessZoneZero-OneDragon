from PySide6.QtCore import QEvent
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtGui import QIcon
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QCompleter
from enum import Enum
from qfluentwidgets import FluentIconBase
from qfluentwidgets import ToolTip
from typing import Optional, List, Iterable
from typing import Union

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.editable_combo_box import EditableComboBox
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class EditableComboBoxSettingCard(SettingCardBase):
    """包含下拉框的可输入自定义设置卡片类。"""


    value_changed = Signal(int, object)

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str]=None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 options_enum: Optional[Iterable[Enum]] = None,
                 options_list: Optional[List[ConfigItem]] = None,
                 input_placeholder: Optional[str] = None,
                 tooltip: Optional[str] = None,
                 adapter: Optional[YamlConfigAdapter] = None,
                 parent=None
                 ):
        SettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size,
            margins=margins,
            parent=parent
        )

        # 初始化下拉框
        self.combo_box = EditableComboBox(self)
        self.combo_box.setPlaceholderText(input_placeholder)
        self.hBoxLayout.addWidget(self.combo_box, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.adapter: YamlConfigAdapter = adapter

        # 处理工具提示
        self.tooltip_text: str = tooltip
        self._tooltip: Optional[ToolTip] = None
        if self.with_tooltip:
            self.titleLabel.installEventFilter(self)

        # 初始化选项
        self._opts_list: List[ConfigItem] = []
        self._initialize_options(options_enum, options_list)

        # 设置初始索引
        self.last_index = -1
        if self.combo_box.count() > 0:
            self.combo_box.setCurrentIndex(0)
            self.last_index = 0

        # 连接信号与槽
        self.combo_box.currentIndexChanged.connect(self._on_index_changed)

    def _initialize_options(self, options_enum: Optional[Iterable[Enum]], options_list: Optional[List[ConfigItem]]) -> None:
        """从枚举或列表初始化下拉框选项。"""
        if options_list is not None:
            self.set_options_by_list(options_list)
        elif options_enum is not None:
            options_list = [
                opt.value
                for opt in options_enum
                if isinstance(opt.value, ConfigItem)
            ]
            self.set_options_by_list(options_list)
        else:
            self.set_options_by_list([])

    def eventFilter(self, obj, event: QEvent) -> bool:
        """处理标题标签的鼠标事件。"""
        if obj == self.titleLabel:
            if event.type() == QEvent.Type.Enter:
                self._show_tooltip()
            elif event.type() == QEvent.Type.Leave:
                self._hide_tooltip()
        return super().eventFilter(obj, event)

    @property
    def with_tooltip(self) -> bool:
        """
        是否有tooltip
        @return:
        """
        return self.tooltip_text is not None and len(self.tooltip_text) > 0

    def _show_tooltip(self) -> None:
        """显示工具提示。"""
        if self.with_tooltip:
            if self._tooltip:
                self._tooltip.close()
            self._tooltip = ToolTip(self.tooltip_text, self)
            self._tooltip.shadowEffect.setColor(QColor(0, 0, 0, 15))
            self._tooltip.shadowEffect.setOffset(0, 1)
            self._tooltip.setDuration(0)

            # 计算工具提示位置
            label_pos = self.titleLabel.mapToGlobal(self.titleLabel.rect().topLeft())
            x = label_pos.x() - 64
            y = label_pos.y() - self._tooltip.size().height() - 10
            self._tooltip.move(x, y)
            self._tooltip.show()

    def _hide_tooltip(self) -> None:
        """隐藏工具提示。"""
        if self._tooltip:
            self._tooltip.close()
            self._tooltip = None

    def set_options_by_list(self, options: List[ConfigItem]) -> None:
        """通过 ConfigItem 列表设置下拉框选项。"""
        self.combo_box.blockSignals(True)
        self.combo_box.clear()
        self._opts_list.clear()

        for opt_item in options:
            self._opts_list.append(opt_item)
            self.combo_box.addItem(opt_item.ui_text, userData=opt_item.value)
        self.set_completer_options(options)

        self.combo_box.blockSignals(False)

    def init_with_adapter(self, adapter: Optional[YamlConfigAdapter]) -> None:
        """初始化配置适配器。"""
        self.adapter = adapter
        self.setValue(None if adapter is None else adapter.get_value(), emit_signal=False)

    def set_completer_options(self, options_list: List[ConfigItem]) -> None:
        """初始化自动补全器。"""
        completion_strings = [item.ui_text for item in options_list]
        completer = QCompleter(completion_strings)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)  # 设置大小写不敏感
        completer.setFilterMode(Qt.MatchFlag.MatchContains)  # 设置匹配模式为包含
        self.combo_box.setCompleter(completer)

    def _on_index_changed(self, index: int) -> None:
        """索引变化时发射信号。"""
        if index == self.last_index:
            return

        self.last_index = index
        self._update_desc()
        val = self.combo_box.itemData(index)

        if self.adapter is not None:
            self.adapter.set_value(val)

        self.value_changed.emit(index, val)

    def _update_desc(self) -> None:
        """更新描述显示。"""
        if self.combo_box.currentIndex() >= 0:
            desc = self._opts_list[self.combo_box.currentIndex()].desc
            self.setContent(desc)

    def setValue(self, value: object, emit_signal: bool = True) -> None:
        """设置下拉框的值。"""
        if not emit_signal:
            self.combo_box.blockSignals(True)

        if value is None:
            self.last_index = -1
            self.combo_box.setCurrentIndex(-1)
        else:
            for idx in range(self.combo_box.count()):
                if self.combo_box.itemData(idx) == value:
                    self.last_index = idx
                    self.combo_box.setCurrentIndex(idx)
                    break

        if not emit_signal:
            self.combo_box.blockSignals(False)
        self._update_desc()

    def getValue(self) -> object:
        """获取当前选中的值。"""
        return self.combo_box.itemData(self.combo_box.currentIndex())
