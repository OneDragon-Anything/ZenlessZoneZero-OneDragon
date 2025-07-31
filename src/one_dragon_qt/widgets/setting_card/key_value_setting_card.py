import json
from typing import Union, List, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit
from qfluentwidgets import FluentIcon, FluentIconBase, LineEdit

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase


class KeyValueSettingCard(SettingCardBase):
    """ 可动态增删的键值对设置卡片 """

    value_changed = Signal(str)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase],
                 title: str,
                 content: Optional[str] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(icon, title, content, parent=parent)

        self.vBoxLayout.setSpacing(8)

        # 主布局，包含一个用于显示键值对的垂直布局和一个添加按钮
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)
        self.hBoxLayout.addLayout(self.main_layout)

        self.kv_layout = QVBoxLayout()  # 存放键值对行
        self.main_layout.addLayout(self.kv_layout)

        self.add_btn = QPushButton(gt('添加一行', 'ui'), self)
        self.add_btn.setIcon(FluentIcon.ADD.icon())
        self.add_btn.clicked.connect(lambda: self._add_row())
        self.main_layout.addWidget(self.add_btn, 0, Qt.AlignmentFlag.AlignLeft)

        # 不在初始化时设置固定高度，让它动态调整
        # self.setFixedHeight(self.sizeHint().height())
        
        # 默认添加一行空白，方便用户输入
        self._add_row(emit_signal=False)

    def _add_row(self, key="", value="", emit_signal=True):
        """ 添加一行键值对输入 """
        row_widget = QWidget(self)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        key_edit = LineEdit(self)
        key_edit.setPlaceholderText(gt('键', 'ui'))
        key_edit.setText(key)
        if emit_signal:
            key_edit.textChanged.connect(self._on_value_changed)

        value_edit = LineEdit(self)
        value_edit.setPlaceholderText(gt('值', 'ui'))
        value_edit.setText(value)
        if emit_signal:
            value_edit.textChanged.connect(self._on_value_changed)

        remove_btn = QPushButton(self)
        remove_btn.setIcon(FluentIcon.DELETE.icon())
        remove_btn.setFixedSize(30, 30)
        remove_btn.clicked.connect(lambda: self._remove_row(row_widget))

        row_layout.addWidget(key_edit)
        row_layout.addWidget(value_edit)
        row_layout.addWidget(remove_btn)

        self.kv_layout.addWidget(row_widget)
        self._update_height()

    def _remove_row(self, row_widget: QWidget):
        """ 移除指定行 """
        self.kv_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self._on_value_changed()
        self._update_height()

    def _clear_rows(self):
        """ 清空所有行 """
        while self.kv_layout.count():
            child = self.kv_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _update_height(self):
        """ 根据内容更新卡片高度 """
        # 计算所需的高度
        min_height = 100  # 最小高度
        content_height = self.kv_layout.count() * 40 + 80  # 每行大约40px，加上按钮和间距
        new_height = max(min_height, content_height)
        
        self.setMinimumHeight(new_height)
        self.setMaximumHeight(new_height)
        
        # 通知父组件更新布局
        parent = self.parent()
        if parent:
            from PySide6.QtWidgets import QWidget
            if isinstance(parent, QWidget):
                parent.update()
                parent.updateGeometry()

    def _on_value_changed(self):
        self.value_changed.emit(self.getValue())

    def getValue(self) -> str:
        """ 获取所有键值对，返回 JSON 格式的字符串 """
        kv_dict = {}
        for i in range(self.kv_layout.count()):
            row_widget = self.kv_layout.itemAt(i).widget()
            if row_widget:
                line_edits = list(row_widget.findChildren(QLineEdit))
                if len(line_edits) >= 2:
                    key_edit = line_edits[0]
                    value_edit = line_edits[1]
                    if key_edit.text().strip():
                        kv_dict[key_edit.text().strip()] = value_edit.text().strip()
        return json.dumps(kv_dict, ensure_ascii=False)

    def setValue(self, value: str):
        """ 从 JSON 字符串设置键值对 """
        self._clear_rows()
        try:
            if value:
                data = json.loads(value)
                if isinstance(data, dict):
                    for key, val in data.items():
                        self._add_row(key, str(val), emit_signal=False)
                elif isinstance(data, list):
                    # 兼容旧的列表格式
                    for item in data:
                        if isinstance(item, dict):
                            self._add_row(item.get("key", ""), item.get("value", ""), emit_signal=False)
                
                # 如果有数据但没有添加任何行，添加一个空行
                if self.kv_layout.count() == 0:
                    self._add_row(emit_signal=False)
            else:
                # 如果值为空，添加一个空行
                self._add_row(emit_signal=False)
        except (json.JSONDecodeError, TypeError):
            # 如果值无效，则添加一个空行
            self._add_row(emit_signal=False)
        
        # 最后更新一次，但不触发值变化事件
        self._update_height()

    def init_with_adapter(self, adapter):
        """ 使用适配器初始化 """
        self.adapter = adapter
        self.setValue(adapter.get_value())
        self.value_changed.connect(lambda val: adapter.set_value(val))
