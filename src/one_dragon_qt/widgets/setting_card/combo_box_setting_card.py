from collections.abc import Iterable
from enum import Enum

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QLabel
from qfluentwidgets import FluentIconBase, ToolTip, isDarkTheme

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import IconSize, Margins
from one_dragon_qt.widgets.adapter_init_mixin import AdapterInitMixin
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase


class ComboBoxSettingCard(SettingCardBase, AdapterInitMixin):
    """包含下拉框的自定义设置卡片类。"""


    value_changed = Signal(int, object)

    def __init__(self,
                 icon: str | QIcon | FluentIconBase, title: str, content: str | None=None,
                 icon_size: IconSize | None = None,
                 margins: Margins | None = None,
                 options_enum: Iterable[Enum] | None = None,
                 options_list: list[ConfigItem] | None = None,
                 tooltip: str | None = None,
                 parent=None
                 ):

        SettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size if icon_size is not None else IconSize(16, 16),
            margins=margins if margins is not None else Margins(16, 16, 0, 16),
            parent=parent
        )
        AdapterInitMixin.__init__(self)
        self.default_content = content

        # 选项小标签（ConfigItem.tag），样式同标题栏的「集成/源码」标签；没有 tag 时隐藏
        self.tag_label = QLabel(self)
        self.tag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 固定高度，否则会被卡片布局纵向拉伸成竖长的方块
        self.tag_label.setFixedHeight(20)
        self.tag_label.setVisible(False)
        self.hBoxLayout.addWidget(self.tag_label, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)

        # 初始化下拉框
        self.combo_box = ComboBox(self)
        self.hBoxLayout.addWidget(self.combo_box, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        # 处理工具提示
        self.tooltip_text: str = tooltip
        self._tooltip: ToolTip | None = None
        if self.with_tooltip:
            self.titleLabel.installEventFilter(self)

        # 初始化选项
        self._opts_list: list[ConfigItem] = []
        self._initialize_options(options_enum, options_list)

        # 设置初始索引
        self.last_index = -1
        if self.combo_box.count() > 0:
            self.combo_box.setCurrentIndex(0)
            self.last_index = 0

        # 连接信号与槽
        self.combo_box.currentIndexChanged.connect(self._on_index_changed)

    def _initialize_options(self, options_enum: Iterable[Enum] | None, options_list: list[ConfigItem] | None) -> None:
        """从枚举或列表初始化下拉框选项。"""
        if options_enum:
            for opt in options_enum:
                if isinstance(opt.value, ConfigItem):
                    self._opts_list.append(opt.value)
                    self.combo_box.addItem(opt.value.ui_text, userData=opt.value.value)
        elif options_list:
            for opt_item in options_list:
                self._opts_list.append(opt_item)
                self.combo_box.addItem(opt_item.ui_text, userData=opt_item.value)

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
            self._tooltip = ToolTip(gt(self.tooltip_text), self)
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

    def set_options_by_list(self, options: list[ConfigItem]) -> None:
        """通过 ConfigItem 列表设置下拉框选项。"""
        self.combo_box.blockSignals(True)
        self.combo_box.clear()
        self._opts_list.clear()

        for opt_item in options:
            self._opts_list.append(opt_item)
            self.combo_box.addItem(opt_item.ui_text, userData=opt_item.value)

        self.combo_box.blockSignals(False)

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
            if desc is None or len(desc) == 0:
                desc = self.default_content
            self.setContent(desc)
        self._update_tag()

    def _update_tag(self) -> None:
        """按当前选中项的 tag 更新小标签。"""
        index = self.combo_box.currentIndex()
        tag = self._opts_list[index].tag if 0 <= index < len(self._opts_list) else ''
        self.tag_label.setVisible(bool(tag))
        if not tag:
            return
        self.tag_label.setText(gt(tag))
        text_color = 'white' if isDarkTheme() else '#333333'
        self.tag_label.setStyleSheet(
            f"color: {text_color}; background-color: rgba(128, 128, 128, 76);"
            " border-radius: 10px; padding: 0px 10px;"
            " font: 13px 'Segoe UI', 'Microsoft YaHei', 'PingFang SC';"
        )

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
