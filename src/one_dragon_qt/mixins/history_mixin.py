from typing import Optional, Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from qfluentwidgets import FluentIcon, PushButton
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard


class HistoryMixin:
    """
    历史记录功能的混入类，提供撤回/恢复功能

    使用此Mixin的类需要：
    1. 在__init__中调用_init_history()
    2. 实现抽象方法：_has_valid_context(), _apply_undo(), _apply_redo()
    3. 可选实现：_handle_specific_keys()
    4. 在需要记录历史时调用_add_history_record()
    """

    def _init_history(self) -> None:
        """初始化历史记录相关属性，需要在子类的__init__中调用"""
        self.history: list = []
        self.history_index: int = -1
        self.undo_btn: Optional[PushButton] = None
        self.redo_btn: Optional[PushButton] = None
        self.history_opt: Optional[MultiPushSettingCard] = None

    def _create_history_ui(self) -> MultiPushSettingCard:
        """
        创建历史记录相关的UI组件
        :return: 包含撤回/恢复按钮的设置卡片
        """
        self.undo_btn = PushButton(gt('撤回'))
        self.undo_btn.setIcon(FluentIcon.CANCEL)
        self.undo_btn.clicked.connect(self._on_undo_clicked)
        self.undo_btn.setEnabled(False)

        self.redo_btn = PushButton(gt('恢复'))
        self.redo_btn.setIcon(FluentIcon.SYNC)
        self.redo_btn.clicked.connect(self._on_redo_clicked)
        self.redo_btn.setEnabled(False)

        self.history_opt = MultiPushSettingCard(
            icon=FluentIcon.HISTORY,
            title='历史记录',
            content='Ctrl+Z 撤回，Ctrl+Shift+Z 恢复',
            btn_list=[self.undo_btn, self.redo_btn]
        )

        self._update_undo_button_text()
        self._update_redo_button_text()

        return self.history_opt

    def _update_undo_button_text(self) -> None:
        """更新撤回按钮的文本，显示可撤回的次数"""
        if self.undo_btn is None:
            return

        undo_count = self.history_index + 1
        if undo_count == 0:
            self.undo_btn.setText(gt('撤回'))
            self.undo_btn.setEnabled(False)
        else:
            self.undo_btn.setText(f"{gt('撤回')} ({undo_count})")
            self.undo_btn.setEnabled(True)

    def _update_redo_button_text(self) -> None:
        """更新恢复按钮的文本，显示可恢复的次数"""
        if self.redo_btn is None:
            return

        redo_count = len(self.history) - self.history_index - 1
        if redo_count == 0:
            self.redo_btn.setText(gt('恢复'))
            self.redo_btn.setEnabled(False)
        else:
            self.redo_btn.setText(f"{gt('恢复')} ({redo_count})")
            self.redo_btn.setEnabled(True)

    def _update_history_buttons(self) -> None:
        """更新历史记录按钮的状态"""
        self._update_undo_button_text()
        self._update_redo_button_text()

    def _clear_history(self) -> None:
        """清除撤回和恢复历史"""
        self.history.clear()
        self.history_index = -1
        self._update_undo_button_text()
        self._update_redo_button_text()

    def _add_history_record(self, change_record: Dict[str, Any]) -> None:
        """
        添加历史记录
        :param change_record: 变化记录字典
        """
        # 如果当前不在历史末尾，移除后续的历史记录
        if self.history_index + 1 < len(self.history):
            self.history = self.history[:self.history_index + 1]

        # 添加新的变化记录
        self.history.append(change_record)
        self.history_index = len(self.history) - 1

        self._update_undo_button_text()
        self._update_redo_button_text()

    def _on_undo_clicked(self) -> None:
        """撤回上一次操作"""
        if self.history_index < 0 or not self._has_valid_context():
            return

        # 获取当前操作记录
        current_change = self.history[self.history_index]

        # 应用撤回操作
        self._apply_undo(current_change)

        # 向前移动历史指针
        self.history_index -= 1

        # 更新按钮状态
        self._update_undo_button_text()
        self._update_redo_button_text()

    def _on_redo_clicked(self) -> None:
        """恢复上一次撤回的操作"""
        if self.history_index + 1 >= len(self.history) or not self._has_valid_context():
            return

        # 向后移动历史指针
        self.history_index += 1

        # 获取要恢复的操作记录
        current_change = self.history[self.history_index]

        # 应用恢复操作
        self._apply_redo(current_change)

        # 更新按钮状态
        self._update_undo_button_text()
        self._update_redo_button_text()

    def history_key_press_event(self, event: QKeyEvent) -> bool:
        """
        处理历史记录相关的键盘快捷键
        :param event: 键盘事件
        :return: 如果事件被处理返回True，否则返回False
        """
        if not self._has_valid_context():
            return False

        # Ctrl+Shift+Z 恢复操作
        if (event.key() == Qt.Key.Key_Z and
            event.modifiers() & Qt.KeyboardModifier.ControlModifier and
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self._on_redo_clicked()
            event.accept()
            return True

        # Ctrl+Z 撤销操作
        if (event.key() == Qt.Key.Key_Z and
            event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._on_undo_clicked()
            event.accept()
            return True

        # 处理子类特定的快捷键
        return self._handle_specific_keys(event)

    def _handle_specific_keys(self, event: QKeyEvent) -> bool:
        """
        处理子类特定的键盘快捷键
        :param event: 键盘事件
        :return: 如果事件被处理返回True，否则返回False
        """
        return False

    def _has_valid_context(self) -> bool:
        """
        检查是否有有效的操作上下文
        :return: 是否可以进行撤回/恢复操作
        """
        raise NotImplementedError("子类必须实现 _has_valid_context 方法")

    def _apply_undo(self, change_record: Dict[str, Any]) -> None:
        """
        应用撤回操作
        :param change_record: 历史记录
        """
        raise NotImplementedError("子类必须实现 _apply_undo 方法")

    def _apply_redo(self, change_record: Dict[str, Any]) -> None:
        """
        应用恢复操作
        :param change_record: 历史记录
        """
        raise NotImplementedError("子类必须实现 _apply_redo 方法")
