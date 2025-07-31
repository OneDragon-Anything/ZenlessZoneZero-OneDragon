import json
from typing import Union, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import FluentIcon, FluentIconBase, LineEdit, PushButton, ToolButton

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class KeyValueSettingCard(SettingCardBase):
    """可动态增删的键值对设置卡片"""

    value_changed = Signal(str)

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str] = None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 adapter: Optional[YamlConfigAdapter] = None,
                 parent: Optional[QWidget] = None):

        SettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size,
            margins=margins,
            parent=parent
        )

        self.adapter: YamlConfigAdapter = adapter
        self.vBoxLayout.setSpacing(8)

        # 主布局，包含一个用于显示键值对的垂直布局和一个添加按钮
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)
        self.hBoxLayout.addLayout(self.main_layout)

        self.kv_layout = QVBoxLayout()  # 存放键值对行
        self.main_layout.addLayout(self.kv_layout)

        self.add_btn = PushButton(FluentIcon.ADD, gt('新增'), self)
        self.add_btn.clicked.connect(lambda: self._add_row())

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addSpacing(16)

        self.main_layout.addLayout(btn_layout)

        # 默认添加一行空白，方便用户输入
        self._add_row(emit_signal=False)

    def _add_row(self, key="", value="", emit_signal=True):
        """添加一行键值对输入"""
        row_widget = QWidget(self)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        key_edit = LineEdit(self)
        key_edit.setPlaceholderText(gt('键', 'ui'))
        key_edit.setText(key)

        key_edit.editingFinished.connect(self._on_value_changed)

        value_edit = LineEdit(self)
        value_edit.setPlaceholderText(gt('值', 'ui'))
        value_edit.setText(value)

        value_edit.editingFinished.connect(self._on_value_changed)

        remove_btn = ToolButton(FluentIcon.DELETE, self)
        remove_btn.setFixedSize(30, 30)
        remove_btn.clicked.connect(lambda: self._remove_row(row_widget))
        remove_btn.setEnabled(self.kv_layout.count() > 0)

        row_layout.addWidget(key_edit)
        row_layout.addWidget(value_edit)
        row_layout.addWidget(remove_btn)
        row_layout.addSpacing(16)

        self.kv_layout.addWidget(row_widget)
        self._update_height()
        self._update_all_remove_buttons()

    def _remove_row(self, row_widget: QWidget):
        """移除指定行"""
        if self.kv_layout.count() <= 1:
            return

        self.kv_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self._on_value_changed()
        self._update_height()
        self._update_all_remove_buttons()

    def _clear_rows(self):
        """清空所有行"""
        while self.kv_layout.count():
            child = self.kv_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _update_height(self):
        """根据内容更新卡片高度"""
        # 计算所需的高度
        min_height = 100  # 最小高度
        content_height = self.kv_layout.count() * 40 + 80  # 每行大约40px，加上按钮和间距
        new_height = max(min_height, content_height)
        self.setFixedHeight(new_height)

    def _update_all_remove_buttons(self):
        """更新所有删除按钮状态"""
        should_enable = self.kv_layout.count() > 1
        for i in range(self.kv_layout.count()):
            row_widget = self.kv_layout.itemAt(i).widget()
            if row_widget:
                remove_btn = row_widget.findChild(ToolButton)
                if remove_btn:
                    remove_btn.setEnabled(should_enable)

    def _block_signals(self, value: bool):
        """断开所有输入框的信号连接"""
        for i in range(self.kv_layout.count()):
            row_widget = self.kv_layout.itemAt(i).widget()
            if row_widget:
                line_edits = list(row_widget.findChildren(LineEdit))
                for line_edit in line_edits:
                    line_edit.blockSignals(value)

    def _on_value_changed(self):
        val = self.getValue()

        if self.adapter is not None:
            self.adapter.set_value(val)

        self.value_changed.emit(val)

    def getValue(self) -> str:
        """获取所有键值对，返回 JSON 格式的字符串"""
        kv_dict = {}
        for i in range(self.kv_layout.count()):
            row_widget = self.kv_layout.itemAt(i).widget()
            if row_widget:
                line_edits = list(row_widget.findChildren(LineEdit))
                if len(line_edits) >= 2:
                    key_edit = line_edits[0]
                    value_edit = line_edits[1]
                    if key_edit.text().strip():
                        kv_dict[key_edit.text().strip()] = value_edit.text().strip()
        return json.dumps(kv_dict, ensure_ascii=False)

    def setValue(self, value: str, emit_signal: bool = True):
        """从 JSON 字符串设置键值对"""
        if not emit_signal:
            self._block_signals(True)

        self._clear_rows()
        try:
            if value:
                data = json.loads(value)
                for key, val in data.items():
                    self._add_row(key, str(val), emit_signal=emit_signal)

                # 如果有数据但没有添加任何行，添加一个空行
                if self.kv_layout.count() == 0:
                    self._add_row(emit_signal=emit_signal)
            else:
                # 如果值为空，添加一个空行
                self._add_row(emit_signal=emit_signal)
        except (json.JSONDecodeError, TypeError):
            # 如果值无效，则添加一个空行
            self._add_row(emit_signal=emit_signal)

        # 最后更新一次，但不触发值变化事件
        self._update_height()
        self._update_all_remove_buttons()

        if not emit_signal:
            # 重新连接信号
            self._block_signals(False)

    def init_with_adapter(self, adapter: Optional[YamlConfigAdapter]) -> None:
        """使用配置适配器初始化值"""
        self.adapter = adapter

        if self.adapter is None:
            self.setValue("", emit_signal=False)
        else:
            self.setValue(self.adapter.get_value(), emit_signal=False)

        if self.adapter is not None:
            self.value_changed.connect(lambda val: self.adapter.set_value(val))
