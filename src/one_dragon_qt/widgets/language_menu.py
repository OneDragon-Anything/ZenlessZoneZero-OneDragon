from PySide6.QtCore import Signal
from qfluentwidgets import RoundMenu, Action, FluentIcon, Dialog
from one_dragon.utils import app_utils
from one_dragon.utils.i18_utils import gt
from one_dragon.base.config.custom_config import UILanguageEnum


class LanguageMenu(RoundMenu):
    """语言切换菜单"""

    language_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._init_menu()

    def _init_menu(self):
        """初始化菜单"""
        # 添加语言选项
        for lang_enum in UILanguageEnum:
            action = Action(
                FluentIcon.LANGUAGE,
                lang_enum.value.label,
                self
            )
            action.triggered.connect(lambda checked, lang=lang_enum.value.value: self._on_language_selected(lang))
            self.addAction(action)

    def _on_language_selected(self, language: str):
        """当选择语言时触发"""
        self.language_changed.emit(language)
        self.hide()

        # 显示语言切换成功确认对话框
        dialog = Dialog(gt('提示', 'ui', language), gt('语言切换成功，需要重启应用程序以生效', 'ui', language))
        dialog.setTitleBarVisible(False)
        dialog.yesButton.setText(gt('立即重启', 'ui', language))
        dialog.cancelButton.setText(gt('稍后重启', 'ui', language))

        if dialog.exec():
            app_utils.start_one_dragon(True)
