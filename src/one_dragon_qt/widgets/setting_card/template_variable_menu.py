from qfluentwidgets import RoundMenu, Action, FluentIcon
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from .template_variables import TemplateVariables


class TemplateVariableMenu(RoundMenu):
    """模板变量选择菜单"""

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
            action.triggered.connect(lambda checked, v=var_config['key']: self._insert_variable(v))
            self.addAction(action)

        # 添加分隔线
        self.addSeparator()

        # 添加完整模板选项
        full_template_action = Action(
            FluentIcon.CODE,
            gt("完整模板"),
            self
        )
        full_template_action.triggered.connect(self._insert_full_template)
        self.addAction(full_template_action)


    def _insert_variable(self, variable: str):
        """在光标位置插入变量"""
        if not hasattr(self.editor, 'textCursor'):
            log.warning("编辑器不支持光标操作")
            return

        cursor = self.editor.textCursor()
        if cursor is None:
            log.warning("无法获取文本光标")
            return

            # 插入变量
        cursor.insertText(variable)
        self.editor.setTextCursor(cursor)

        # 触发文本变化事件
        self._trigger_text_changed()

    def _insert_full_template(self):
        """插入完整模板"""

        # 构建完整模板内容
        template_content = self._build_full_template_content()

        # 在光标位置插入模板
        cursor = self.editor.textCursor()
        cursor.insertText(template_content)
        self.editor.setTextCursor(cursor)

        # 触发文本变化事件
        self._trigger_text_changed()


    def _build_full_template_content(self) -> str:
        """构建完整模板内容"""
        # 检查父组件类型来决定模板格式
        parent = self.parent()
        while parent:
            if hasattr(parent, '__class__'):
                class_name = parent.__class__.__name__
                if 'Dialog' in class_name:
                    # 对话框使用JSON格式
                    return '{\n  "title": "$title",\n  "content": "$content",\n  "image": "$image"\n}'
                elif 'SettingCard' in class_name:
                    # 设置卡片使用纯文本格式
                    return "标题: $title\n内容: $content\n图片: $image"
            parent = parent.parent() if hasattr(parent, 'parent') else None

        # 默认使用纯文本格式
        return "标题: $title\n内容: $content\n图片: $image"

    def _trigger_text_changed(self):
        """触发文本变化事件"""
        # 检查编辑器是否有textChanged信号
        if hasattr(self.editor, 'textChanged'):
            # 手动触发textChanged信号
            self.editor.textChanged.emit()

        # 查找CodeEditorSettingCard实例来触发相关事件
        parent = self.parent()
        while parent:
            if hasattr(parent, '__class__'):
                class_name = parent.__class__.__name__
                if 'CodeEditorSettingCard' in class_name:
                    # 对于CodeEditorSettingCard，需要触发adapter和value_changed
                    if hasattr(parent, 'adapter') and parent.adapter is not None:
                            parent.adapter.set_value(self.editor.toPlainText())
                    if hasattr(parent, 'value_changed'):
                            parent.value_changed.emit(self.editor.toPlainText())
                    break
                elif hasattr(parent, '_on_text_changed'):
                    parent._on_text_changed()
                    break
            parent = parent.parent() if hasattr(parent, 'parent') else None
