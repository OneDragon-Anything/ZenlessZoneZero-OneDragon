import json
from typing import Union, Optional

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from qfluentwidgets import PlainTextEdit, FluentIconBase, FluentIcon

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon.utils.log_utils import log

class JsonHighlighter(QSyntaxHighlighter):
    """ JSON 语法高亮器 """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.highlighting_rules = []

        # 关键字 (true, false, null)
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#c586c0"))
        keywords = ["\\btrue\\b", "\\bfalse\\b", "\\bnull\\b"]
        for word in keywords:
            pattern = QRegularExpression(word)
            self.highlighting_rules.append((pattern, keyword_format))

        # 键 (字符串，在冒号前)
        key_format = QTextCharFormat()
        key_format.setForeground(QColor("#9cdcfe"))
        self.highlighting_rules.append((QRegularExpression('\".*?\"(?=\\s*:)'), key_format))

        # 字符串
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        self.highlighting_rules.append((QRegularExpression('\".*?\"'), string_format))

        # 数字
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        self.highlighting_rules.append((QRegularExpression("\\b-?[0-9]+(\\.[0-9]+)?([eE][-+]?[0-9]+)?\\b"), number_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)


class CodeEditorSettingCard(SettingCardBase):
    """ 带代码编辑器的设置卡片 """

    def __init__(self, icon: Union[str, QIcon, FluentIconBase],
                 title: str,
                 content: Optional[str] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(icon, title, content, parent=parent)

        self.editor = PlainTextEdit(self)
        self.editor.setPlaceholderText("请输入 JSON 格式的请求体")

        # 设置等宽字体，按优先级选择
        font_families = ["Microsoft YaHei", "Segoe UI", "Consolas", "Monaco", "DejaVu Sans Mono", "Courier New"]
        font = QFont()
        for family in font_families:
            font.setFamily(family)
            if font.exactMatch():
                break
        font.setPointSize(10)
        self.editor.setFont(font)
        self.editor.setMinimumHeight(150)

        self.highlighter = JsonHighlighter(self.editor.document())

        # 创建按钮布局
        button_layout = QVBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)

        # 格式化按钮
        self.format_btn = QPushButton(self)
        self.format_btn.setIcon(FluentIcon.BROOM.icon())
        self.format_btn.setMaximumWidth(80)
        self.format_btn.clicked.connect(self._format_json)
        button_layout.addWidget(self.format_btn)

        button_layout.addStretch()

        self.hBoxLayout.addWidget(self.editor)
        self.hBoxLayout.addLayout(button_layout)

        self.editor.textChanged.connect(self._on_value_changed)

        self.setFixedHeight(self.sizeHint().height())

        # 初始化默认值属性
        self._default_value = None

    def _on_value_changed(self):
        if hasattr(self, 'adapter'):
            self.adapter.set_value(self.getValue())

    def getValue(self) -> str:
        return self.editor.toPlainText()

    def setValue(self, value: str):
        try:
            # 格式化 JSON
            pretty_json = json.dumps(json.loads(value), indent=4, ensure_ascii=False)
            self.editor.setPlainText(pretty_json)
        except (json.JSONDecodeError, TypeError):
            self.editor.setPlainText(value) # 如果格式不正确，则直接显示原文

    def init_with_adapter(self, adapter):
        self.adapter = adapter
        current_value = adapter.get_value() if adapter else ""
        # 如果配置值为空且有默认值，使用默认值
        if not current_value and hasattr(self, '_default_value') and self._default_value:
            self.setValue(self._default_value)
        else:
            self.setValue(current_value or "")

    def _format_json(self):
        """格式化 JSON 内容"""
        try:
            current_text = self.editor.toPlainText().strip()
            if current_text:
                # 尝试解析并格式化 JSON
                parsed_json = json.loads(current_text)
                formatted_json = json.dumps(parsed_json, indent=4, ensure_ascii=False)
                self.editor.setPlainText(formatted_json)
        except json.JSONDecodeError:
            # 如果不是有效的 JSON，不做处理
            pass
        except Exception:
            log.error('格式化 JSON 失败', exc_info=True)
