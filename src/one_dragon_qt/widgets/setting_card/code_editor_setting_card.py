import json
from typing import Union, Optional

from PySide6.QtCore import QRegularExpression, Signal, Qt, QRect
from PySide6.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter, QIcon, QKeyEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import QSize
from qfluentwidgets import PlainTextEdit, FluentIconBase, FluentIcon, ToolButton, MessageBoxBase, SubtitleLabel,\
                           BodyLabel, isDarkTheme, ToolTipFilter, ToolTipPosition, RoundMenu, Action

from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log


class TemplateVariables:
    """模板变量配置类"""

    VARIABLES = [
        {"key": "$title", "name": "标题变量", "icon": FluentIcon.TAG},
        {"key": "$content", "name": "内容变量", "icon": FluentIcon.DOCUMENT},
        {"key": "$image", "name": "图片变量", "icon": FluentIcon.PHOTO},
        {"key": "$timestamp", "name": "时间戳 (2024-12-19 15:30:45)", "icon": FluentIcon.CALENDAR},
        {"key": "$iso_timestamp", "name": "ISO时间戳 (2024-12-19T15:30:45)", "icon": FluentIcon.CALENDAR},
        {"key": "$unix_timestamp", "name": "Unix时间戳 (1703004645)", "icon": FluentIcon.CALENDAR},
    ]

    @classmethod
    def get_variables(cls):
        """获取所有变量配置"""
        return cls.VARIABLES


class TemplateVariableMenu(RoundMenu):
    """模板变量选择菜单"""

    # 定义信号
    variable_selected = Signal(str)  # 选择变量时发出
    template_requested = Signal()    # 请求插入完整模板时发出

    def __init__(self, parent=None, editor=None):
        super().__init__(parent=parent)
        self.editor = editor
        self._setup_menu()

    def _setup_menu(self):
        """设置菜单项"""
        # 获取变量配置
        variables = TemplateVariables.get_variables()

        # 添加变量选项
        for var_config in variables:
            action = Action(
                var_config["icon"],
                f"{var_config['key']} - {gt(var_config['name'])}",
                self
            )
            # 修复闭包问题：使用默认参数捕获当前循环的变量值
            action.triggered.connect(lambda checked=None, v=var_config['key']: self.variable_selected.emit(v))
            self.addAction(action)

        # 添加分隔线
        self.addSeparator()

        # 添加完整模板选项
        full_template_action = Action(
            FluentIcon.CODE,
            gt("完整模板"),
            self
        )
        full_template_action.triggered.connect(lambda: self.template_requested.emit())
        self.addAction(full_template_action)

    def get_template_content(self) -> str:
        """获取完整模板内容供父组件使用"""
        return '{\n  "title": "$title",\n  "content": "$content",\n  "image": "$image"\n}'


class LineNumberArea(QWidget):
    """行号区域"""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.line_labels = []  # 存储BodyLabel实例

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.update_line_numbers(event)

    def update_line_numbers(self, event):
        """使用BodyLabel更新行号显示"""
        # 清除旧的标签
        for label in self.line_labels:
            label.deleteLater()
        self.line_labels.clear()

        # 计算可见的行范围
        block = self.editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top())
        bottom = top + int(self.editor.blockBoundingRect(block).height())
        line_height = self.editor.fontMetrics().height()

        y_offset = 0
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                # 创建BodyLabel显示行号
                line_label = BodyLabel(str(block_number + 1), self)
                line_label.setAlignment(Qt.AlignmentFlag.AlignRight)

                # 设置位置和大小
                label_width = self.editor.line_number_area_width() - 3
                line_label.setGeometry(0, top, label_width, line_height)
                line_label.show()

                self.line_labels.append(line_label)

            block = block.next()
            top = bottom
            bottom = top + int(self.editor.blockBoundingRect(block).height())
            block_number += 1


class CodeEditor(PlainTextEdit):
    """支持行号和tab缩进的代码编辑器"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)

        self.update_line_number_area_width(0)

        # 设置tab缩进为4个空格
        self.setTabStopDistance(40)

    def refresh_theme(self):
        """刷新主题相关的显示"""
        self.line_number_area.update()
        # 如果有语法高亮器，也刷新它
        if hasattr(self, 'document') and self.document():
            highlighter = self.document().syntaxHighlighter()
            if highlighter and hasattr(highlighter, 'update_colors'):
                highlighter.update_colors()
                highlighter.rehighlight()

    def line_number_area_width(self):
        """计算行号区域宽度"""
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, newBlockCount):
        """更新行号区域宽度"""
        self.setViewportMargins(self.line_number_area_width(), 0, 4, 0)

    def update_line_number_area(self, rect, dy):
        """更新行号区域"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        """调整大小事件"""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def keyPressEvent(self, event: QKeyEvent):
        """处理按键事件，支持tab缩进"""
        if event.key() == Qt.Key.Key_Tab:
            cursor = self.textCursor()

            # 检查是否有选中文本
            if cursor.hasSelection():
                # 多行选中时，对每行进行缩进
                start = cursor.selectionStart()
                end = cursor.selectionEnd()

                # 移动到选择开始位置
                cursor.setPosition(start)
                start_block = cursor.blockNumber()

                # 移动到选择结束位置
                cursor.setPosition(end)
                end_block = cursor.blockNumber()

                # 开始编辑
                cursor.beginEditBlock()

                # 对每一行添加缩进
                for block_num in range(start_block, end_block + 1):
                    cursor.setPosition(self.document().findBlockByNumber(block_num).position())
                    cursor.insertText("    ")  # 插入4个空格

                cursor.endEditBlock()

                # 重新选择修改后的文本
                cursor.setPosition(start)
                cursor.setPosition(end + (end_block - start_block + 1) * 4, cursor.MoveMode.KeepAnchor)
                self.setTextCursor(cursor)
                return
            else:
                # 单行时插入4个空格
                cursor.insertText("    ")
                return

        elif event.key() == Qt.Key.Key_Backtab:
            cursor = self.textCursor()

            # 检查是否有选中文本
            if cursor.hasSelection():
                # 多行选中时，对每行减少缩进
                start = cursor.selectionStart()
                end = cursor.selectionEnd()

                # 移动到选择开始位置
                cursor.setPosition(start)
                start_block = cursor.blockNumber()

                # 移动到选择结束位置
                cursor.setPosition(end)
                end_block = cursor.blockNumber()

                # 开始编辑
                cursor.beginEditBlock()

                removed_chars = 0
                # 对每一行移除缩进
                for block_num in range(start_block, end_block + 1):
                    block = self.document().findBlockByNumber(block_num)
                    cursor.setPosition(block.position())
                    cursor.setPosition(block.position() + min(4, block.length() - 1), cursor.MoveMode.KeepAnchor)
                    text = cursor.selectedText()

                    # 计算要移除的空格数
                    spaces_to_remove = 0
                    for char in text:
                        if char == ' ' and spaces_to_remove < 4:
                            spaces_to_remove += 1
                        else:
                            break

                    if spaces_to_remove > 0:
                        cursor.setPosition(block.position())
                        cursor.setPosition(block.position() + spaces_to_remove, cursor.MoveMode.KeepAnchor)
                        cursor.removeSelectedText()
                        removed_chars += spaces_to_remove

                cursor.endEditBlock()

                # 重新选择修改后的文本
                cursor.setPosition(start)
                cursor.setPosition(max(start, end - removed_chars), cursor.MoveMode.KeepAnchor)
                self.setTextCursor(cursor)
                return
            else:
                # 单行时减少缩进
                cursor.select(cursor.SelectionType.LineUnderCursor)
                text = cursor.selectedText()
                if text.startswith("    "):
                    # 移除前4个空格
                    cursor.insertText(text[4:])
                    return

        super().keyPressEvent(event)


class CodeEditorMixin:
    """代码编辑器功能混入类，提供通用的编辑器操作方法"""

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

    def _compact_json(self, text: str) -> str:
        """将JSON内容紧凑化（去除空格和换行）"""
        try:
            if text.strip():
                parsed_json = json.loads(text)
                return json.dumps(parsed_json, separators=(',', ':'), ensure_ascii=False)
            return text
        except json.JSONDecodeError:
            # 如果不是有效的 JSON，返回原文
            return text
        except Exception:
            log.error('紧凑化 JSON 失败', exc_info=True)
            return text

    def _is_compact_json(self, text: str) -> bool:
        """判断JSON是否是紧凑格式（无多余空格和换行）"""
        try:
            if not text.strip():
                return False
            parsed_json = json.loads(text)
            compact_json = json.dumps(parsed_json, separators=(',', ':'), ensure_ascii=False)
            return text.strip() == compact_json
        except json.JSONDecodeError:
            return False
        except Exception:
            return False

    def _show_template_menu(self):
        """显示模板变量菜单"""
        # 计算菜单显示位置
        button_pos = self.template_btn.mapToGlobal(self.template_btn.rect().bottomLeft())
        # 使用非阻塞方式显示菜单，避免与对话框的 exec() 冲突
        self.template_menu.popup(button_pos)

    def _insert_variable(self, variable: str):
        """在光标位置插入变量"""
        self.editor.insertPlainText(variable)

    def _insert_template(self):
        """插入完整模板"""
        template_content = self.template_menu.get_template_content()
        self.editor.insertPlainText(template_content)

    def _create_template_menu_and_button(self, button_layout):
        """创建模板按钮和菜单的通用方法"""
        # 通知模板按钮
        self.template_btn = ToolButton(FluentIcon.TAG, self)
        self.template_btn.clicked.connect(self._show_template_menu)

        # tooltip
        self.template_btn.setToolTip(gt('插入变量'))
        self.template_btn.installEventFilter(ToolTipFilter(self.template_btn, showDelay=500, position=ToolTipPosition.TOP))

        # 创建模板变量菜单，设置父级为按钮的窗口而不是对话框本身
        parent_window = self.parent_window if hasattr(self, 'parent_window') and self.parent_window else self
        self.template_menu = TemplateVariableMenu(parent=parent_window, editor=self.editor)

        # 连接模板菜单信号
        self.template_menu.variable_selected.connect(self._insert_variable)
        self.template_menu.template_requested.connect(self._insert_template)

        button_layout.addWidget(self.template_btn)


class CodeEditorDialog(MessageBoxBase, CodeEditorMixin):
    """代码编辑器弹窗对话框"""

    def __init__(self, parent=None, title: str = "代码编辑器", adapter=None):
        super().__init__(parent)

        self.adapter = adapter

        # 设置标题
        self.titleLabel = SubtitleLabel(gt(title))
        self.viewLayout.addWidget(self.titleLabel)

        # 创建编辑器
        self.editor = CodeEditor(self)
        self.editor.setPlaceholderText(gt("请输入 JSON 格式的请求体"))
        self.editor.setMinimumSize(600, 400)

        # 添加语法高亮
        self.highlighter = JsonHighlighter(self.editor.document())

        # 初始化编辑器内容
        if self.adapter is not None:
            # 如果有适配器，从适配器获取值
            value = self.adapter.get_value()
            # 如果是紧凑的JSON，格式化后显示
            if self._is_compact_json(value):
                try:
                    parsed_json = json.loads(value)
                    formatted_json = json.dumps(parsed_json, indent=4, ensure_ascii=False)
                    self.editor.setPlainText(formatted_json)
                except (json.JSONDecodeError, TypeError):
                    self.editor.setPlainText(value)
            else:
                self.editor.setPlainText(value)

        # 连接文本变化信号到适配器
        if self.adapter is not None:
            self.editor.textChanged.connect(self._on_text_changed)

        # 创建编辑器和按钮的水平布局
        editor_layout = QHBoxLayout()
        editor_layout.addWidget(self.editor)

        # 创建按钮布局
        button_layout = QVBoxLayout()
        button_layout.setContentsMargins(8, 0, 0, 0)
        button_layout.setSpacing(4)

        self.format_btn = ToolButton(FluentIcon.CODE, self)
        self.format_btn.clicked.connect(self._format_json)
        button_layout.addWidget(self.format_btn)

        # 创建模板按钮和菜单
        self._create_template_menu_and_button(button_layout)

        button_layout.addStretch()

        editor_layout.addLayout(button_layout)

        # 创建编辑器容器
        editor_widget = QWidget()
        editor_widget.setLayout(editor_layout)

        # 将编辑器容器添加到主布局
        self.viewLayout.addWidget(editor_widget)
        self.viewLayout.addSpacing(16)

        # 设置按钮文本
        self.yesButton.setText(gt("确定"))
        self.cancelButton.setText(gt("取消"))

    def get_text(self) -> str:
        """获取编辑器中的文本"""
        return self.editor.toPlainText()

    def _on_text_changed(self):
        """文本变化时更新适配器"""
        if self.adapter is not None:
            val = self.editor.toPlainText()
            # 将JSON紧凑化后写入后端
            compact_val = self._compact_json(val)
            self.adapter.set_value(compact_val)


class JsonHighlighter(QSyntaxHighlighter):
    """ JSON 语法高亮器 """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_theme_is_dark = isDarkTheme()
        self.update_colors()

    def update_colors(self):
        """根据主题更新颜色"""
        self.highlighting_rules = []

        if isDarkTheme():
            # 暗色主题颜色
            keyword_color = "#d19ad1"    # 粉紫色
            key_color = "#9cdcfe"        # 浅蓝色
            string_color = "#ce9178"     # 橙色
            number_color = "#b5cea8"     # 浅绿色
        else:
            # 亮色主题颜色（原来的颜色）
            keyword_color = "#c586c0"    # 紫色
            key_color = "#9cdcfe"        # 蓝色
            string_color = "#ce9178"     # 橙色
            number_color = "#b5cea8"     # 绿色

        # 关键字 (true, false, null)
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(keyword_color))
        keywords = ["\\btrue\\b", "\\bfalse\\b", "\\bnull\\b"]
        for word in keywords:
            pattern = QRegularExpression(word)
            self.highlighting_rules.append((pattern, keyword_format))

        # 键 (字符串，在冒号前)
        key_format = QTextCharFormat()
        key_format.setForeground(QColor(key_color))
        self.highlighting_rules.append((QRegularExpression('\".*?\"(?=\\s*:)'), key_format))

        # 字符串
        string_format = QTextCharFormat()
        string_format.setForeground(QColor(string_color))
        self.highlighting_rules.append((QRegularExpression('\".*?\"'), string_format))

        # 数字
        number_format = QTextCharFormat()
        number_format.setForeground(QColor(number_color))
        self.highlighting_rules.append((QRegularExpression("\\b-?[0-9]+(\\.[0-9]+)?([eE][-+]?[0-9]+)?\\b"), number_format))

    def highlightBlock(self, text):
        # 在每次高亮时检查主题是否变化
        current_theme_is_dark = isDarkTheme()
        if current_theme_is_dark != self._current_theme_is_dark:
            self._current_theme_is_dark = current_theme_is_dark
            self.update_colors()

        for pattern, format in self.highlighting_rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)


class CodeEditorSettingCard(SettingCardBase, CodeEditorMixin):
    """ 带代码编辑器的设置卡片 """

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

        self.parent_window = parent
        self.adapter: YamlConfigAdapter = adapter

        # 首先创建编辑器
        self.editor = PlainTextEdit(self)
        self.editor.setPlaceholderText("请输入 JSON 格式的请求体")
        self.highlighter = JsonHighlighter(self.editor.document())

        # 创建按钮布局
        button_layout = QVBoxLayout()
        button_layout.setContentsMargins(16, 16, 16, 16)
        button_layout.setSpacing(4)

        # 弹出按钮
        self.pop_btn = ToolButton(FluentIcon.LINK, self)
        self.pop_btn.clicked.connect(self._pop_editor)
        button_layout.addWidget(self.pop_btn)

        # 格式化按钮
        self.format_btn = ToolButton(FluentIcon.CODE, self)
        self.format_btn.clicked.connect(self._format_json)
        button_layout.addWidget(self.format_btn)

        # 创建模板按钮和菜单
        self._create_template_menu_and_button(button_layout)

        # 创建编辑器和按钮的水平布局
        editor_horizontal_layout = QHBoxLayout()
        editor_horizontal_layout.addWidget(self.editor)
        editor_horizontal_layout.addLayout(button_layout)

        # 创建带上下空隙的垂直布局
        editor_with_spacing_layout = QVBoxLayout()
        editor_with_spacing_layout.setContentsMargins(0, 16, 0, 16)
        editor_with_spacing_layout.addLayout(editor_horizontal_layout)

        # 创建容器widget
        editor_container = QWidget()
        editor_container.setLayout(editor_with_spacing_layout)

        self.hBoxLayout.addWidget(editor_container)
        self.editor.textChanged.connect(self._on_text_changed)

        self.setFixedHeight(self.sizeHint().height())

    def _on_text_changed(self):
        val = self.editor.toPlainText()

        if self.adapter is not None:
            # 将JSON紧凑化后写入后端
            compact_val = self._compact_json(val)
            self.adapter.set_value(compact_val)

        self.value_changed.emit(val)

    def getValue(self) -> str:
        return self.editor.toPlainText()

    def setValue(self, value: str, emit_signal: bool = True):
        if not emit_signal:
            self.editor.blockSignals(True)

        try:
            parsed_json = json.loads(value)
            pretty_json = json.dumps(parsed_json, indent=4, ensure_ascii=False)
            self.editor.setPlainText(pretty_json)
        except (json.JSONDecodeError, TypeError):
            self.editor.setPlainText(value)

        if not emit_signal:
            self.editor.blockSignals(False)

    def init_with_adapter(self, adapter):
        """使用配置适配器初始化值"""
        self.adapter = adapter

        if self.adapter is None:
            self.setValue("", emit_signal=False)
        else:
            self.setValue(self.adapter.get_value(), emit_signal=False)

    def _pop_editor(self):
        """弹出代码编辑器窗口"""
        # 传递适配器给对话框，让对话框直接操作适配器
        dialog = CodeEditorDialog(
            parent=self.parent_window,
            title="JSON 代码编辑器",
            adapter=self.adapter
        )
        dialog.exec()

        # 对话框关闭后，刷新主编辑器显示
        if self.adapter is not None:
            # 从适配器重新获取值并更新显示，不触发信号避免重复写入
            self.setValue(self.adapter.get_value(), emit_signal=False)
