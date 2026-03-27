from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    ToolButton,
)

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiLineSettingCard,
)
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.redemption_code.redemption_code_config import (
    RedemptionCodeConfig,
)

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class CodeCard(MultiLineSettingCard):
    """单个兑换码的卡片"""

    changed = Signal(str, str, int)  # old_code, new_code, end_dt
    deleted = Signal(str)  # code

    def __init__(self, parent=None) -> None:
        self.original_code = ''
        self.is_new = False
        self.readonly = False

        self.code_label = CaptionLabel(text=gt('兑换码'))

        self.code_input = LineEdit()
        self.code_input.setMinimumWidth(150)

        self.end_dt_label = CaptionLabel(text=gt('过期日期'))

        self.end_dt_input = LineEdit()
        self.end_dt_input.setValidator(QIntValidator())
        self.end_dt_input.setMaxLength(8)
        self.end_dt_input.setMinimumWidth(100)

        self.delete_btn = ToolButton(FluentIcon.DELETE)
        self.delete_btn.clicked.connect(self._on_delete_clicked)

        MultiLineSettingCard.__init__(
            self,
            icon=FluentIcon.GAME,
            title='',
            line_list=[
                [self.code_label, self.code_input, self.end_dt_label, self.end_dt_input, self.delete_btn]
            ],
            parent=parent,
        )

        self.code_input.editingFinished.connect(self._on_changed)
        self.end_dt_input.editingFinished.connect(self._on_changed)

    def update_display(self, code: str, end_dt: int, readonly: bool = False, is_new: bool = False) -> None:
        """更新卡片显示内容"""
        self.original_code = code
        self.is_new = is_new
        self.readonly = readonly

        self.code_input.blockSignals(True)
        self.code_input.setText(code)
        self.code_input.setReadOnly(readonly)
        if is_new:
            self.code_input.setPlaceholderText(gt('请输入兑换码'))
        else:
            self.code_input.setPlaceholderText('')
        self.code_input.blockSignals(False)

        self.end_dt_input.blockSignals(True)
        self.end_dt_input.setText(str(end_dt))
        self.end_dt_input.setReadOnly(readonly)
        self.end_dt_input.blockSignals(False)

        self.delete_btn.setVisible(not readonly)

    def _on_changed(self) -> None:
        new_code = self.code_input.text().strip()
        end_dt_str = self.end_dt_input.text().strip()
        try:
            end_dt = int(end_dt_str) if end_dt_str else 20990101
        except ValueError:
            end_dt = 20990101

        if new_code:
            self.changed.emit(self.original_code, new_code, end_dt)

    def _on_delete_clicked(self) -> None:
        self.deleted.emit(self.original_code)


class RedemptionCodeSettingInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='zzz_redemption_code_setting_interface',
            content_widget=None, parent=parent,
            nav_text_cn='兑换码'
        )

    def get_content_widget(self) -> QWidget:
        self.content_widget = Column()

        self.card_container = Column()
        self.content_widget.add_widget(self.card_container)

        self.card_list: list[CodeCard] = []

        self.add_btn = PrimaryPushButton(text=gt('新增'))
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.content_widget.add_widget(self.add_btn, stretch=1)

        return self.content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.config: RedemptionCodeConfig = RedemptionCodeConfig()
        self._update_card_list()

    def _on_add_clicked(self) -> None:
        default_end_dt = int((datetime.now() + timedelta(days=30)).strftime('%Y%m%d'))

        card = CodeCard(parent=self)
        card.update_display('', default_end_dt, is_new=True)
        card.changed.connect(self._on_new_code_entered)
        card.deleted.connect(self._on_new_card_deleted)
        self.card_list.append(card)
        self.card_container.add_widget(card)

        card.code_input.setFocus()

    def _on_new_code_entered(self, old_code: str, new_code: str, end_dt: int) -> None:
        if not new_code:
            return

        if new_code in self.config.codes_dict:
            sender_card = self.sender()
            if sender_card and isinstance(sender_card, CodeCard):
                sender_card.code_input.clear()
                sender_card.code_input.setFocus()
            self._show_warning_toast(gt('兑换码已存在'))
            return

        self.config.add_code(new_code, end_dt)

        sender_card = self.sender()
        if sender_card and isinstance(sender_card, CodeCard):
            sender_card.original_code = new_code
            sender_card.is_new = False
            sender_card.code_input.setPlaceholderText('')
            sender_card.changed.disconnect(self._on_new_code_entered)
            sender_card.deleted.disconnect(self._on_new_card_deleted)
            sender_card.changed.connect(self._on_code_changed)
            sender_card.deleted.connect(self._on_code_deleted)

    def _on_new_card_deleted(self, _code: str) -> None:
        sender_card = self.sender()
        if sender_card and isinstance(sender_card, CodeCard) and sender_card in self.card_list:
            self.card_list.remove(sender_card)
            self.card_container.remove_widget(sender_card)
            sender_card.deleteLater()

    def _on_code_changed(self, old_code: str, new_code: str, end_dt: int) -> None:
        if old_code == new_code:
            self.config.update_code(old_code, new_code, end_dt)
            return

        existing_codes = self.config.codes_dict
        if new_code in existing_codes:
            sender_card = self.sender()
            if sender_card and isinstance(sender_card, CodeCard):
                sender_card.code_input.setText(old_code)
            self._show_warning_toast(gt('兑换码已存在'))
            return

        self.config.update_code(old_code, new_code, end_dt)
        sender_card = self.sender()
        if sender_card and isinstance(sender_card, CodeCard):
            sender_card.original_code = new_code

    def _on_code_deleted(self, code: str) -> None:
        self.config.delete_code(code)
        self._update_card_list()

    def _build_display_list(self) -> list[tuple[str, int, bool]]:
        """构建显示列表 [(code, end_dt, readonly), ...]"""
        result: list[tuple[str, int, bool]] = []
        sample_codes = self.config.sample_codes_dict
        user_codes = self.config.user_codes_dict

        for code, end_dt in sample_codes.items():
            if code in user_codes:
                continue
            result.append((code, end_dt, True))

        for code, end_dt in user_codes.items():
            result.append((code, end_dt, False))

        return result

    def _update_card_list(self) -> None:
        """增量更新卡片列表，复用已有卡片实例"""
        display_list = self._build_display_list()

        # 需要增加卡片
        while len(self.card_list) < len(display_list):
            card = CodeCard(parent=self)
            card.changed.connect(self._on_code_changed)
            card.deleted.connect(self._on_code_deleted)
            self.card_list.append(card)
            self.card_container.add_widget(card)

        # 需要移除多余卡片
        while len(self.card_list) > len(display_list):
            card = self.card_list.pop()
            self.card_container.remove_widget(card)
            card.deleteLater()

        # 更新所有卡片的显示
        for idx, (code, end_dt, readonly) in enumerate(display_list):
            self.card_list[idx].update_display(code, end_dt, readonly=readonly)

    def _show_warning_toast(self, message: str) -> None:
        InfoBar.warning(
            title='',
            content=message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )
