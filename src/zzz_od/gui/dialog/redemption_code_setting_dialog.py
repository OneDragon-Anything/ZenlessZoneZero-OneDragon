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
from zzz_od.application.redemption_code.redemption_code_config import (
    RedemptionCodeConfig,
)
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class CodeCard(MultiLineSettingCard):
    """单个兑换码的卡片，类似体力计划卡片"""

    changed = Signal(str, str, int)  # old_code, new_code, end_dt
    deleted = Signal(str)  # code

    def __init__(self, code: str, end_dt: int, is_new: bool = False, readonly: bool = False, parent=None) -> None:
        self.original_code = code
        self.is_new = is_new  # 是否是新增的空卡片
        self.readonly = readonly  # 是否只读（来自 sample 配置）

        # 兑换码标签
        code_label = CaptionLabel(text=gt('兑换码'))

        # 兑换码输入框
        self.code_input = LineEdit()
        self.code_input.setText(code)
        self.code_input.setMinimumWidth(150)
        if is_new:
            self.code_input.setPlaceholderText(gt('请输入兑换码'))
        if readonly:
            self.code_input.setReadOnly(True)
        else:
            self.code_input.editingFinished.connect(self._on_changed)

        # 过期日期标签
        end_dt_label = CaptionLabel(text=gt('过期日期'))

        # 过期日期输入框
        self.end_dt_input = LineEdit()
        self.end_dt_input.setValidator(QIntValidator())  # 只允许输入数字
        self.end_dt_input.setText(str(end_dt))
        self.end_dt_input.setMinimumWidth(100)
        if readonly:
            self.end_dt_input.setReadOnly(True)
        else:
            self.end_dt_input.editingFinished.connect(self._on_changed)

        # 删除按钮（只读模式下隐藏）
        self.delete_btn = ToolButton(FluentIcon.DELETE)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        if readonly:
            self.delete_btn.hide()

        # 调用父类初始化
        MultiLineSettingCard.__init__(
            self,
            icon=FluentIcon.GAME,
            title='',
            line_list=[
                [code_label, self.code_input, end_dt_label, self.end_dt_input, self.delete_btn]
            ],
            parent=parent
        )

    def _on_changed(self) -> None:
        """内容变化，发出信号但不更新 original_code（由接收者决定是否更新）"""
        new_code = self.code_input.text().strip()
        end_dt_str = self.end_dt_input.text().strip()
        try:
            end_dt = int(end_dt_str) if end_dt_str else 20990101
        except ValueError:
            end_dt = 20990101

        if new_code:
            self.changed.emit(self.original_code, new_code, end_dt)

    def _on_delete_clicked(self) -> None:
        """删除按钮点击"""
        self.deleted.emit(self.original_code)


class RedemptionCodeSettingDialog(AppSettingDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="兑换码配置", parent=parent)
        self.code_cards: list[CodeCard] = []
        self.add_btn: PrimaryPushButton | None = None

    def get_content_widget(self) -> QWidget:
        self.content_widget = Column()

        # 添加按钮
        self.add_btn = PrimaryPushButton(text=gt('新增'))
        self.add_btn.clicked.connect(self._on_add_clicked)

        return self.content_widget

    def on_dialog_shown(self) -> None:
        super().on_dialog_shown()

        # 兑换码配置是全局配置
        self.config: RedemptionCodeConfig = RedemptionCodeConfig()

        # 加载现有兑换码卡片
        self._refresh_code_cards()

    def _on_add_clicked(self) -> None:
        """点击新增按钮，添加一个空的新卡片"""
        default_end_dt = int((datetime.now() + timedelta(days=30)).strftime('%Y%m%d'))

        # 移除添加按钮
        self.content_widget.layout().removeWidget(self.add_btn)

        # 创建新的空卡片
        card = CodeCard(code='', end_dt=default_end_dt, is_new=True, parent=self)
        card.changed.connect(self._on_new_code_entered)
        card.deleted.connect(self._on_new_card_deleted)
        self.code_cards.append(card)
        self.content_widget.add_widget(card)

        # 重新添加按钮
        self.content_widget.add_widget(self.add_btn, stretch=1)

        # 让新卡片的输入框获取焦点
        card.code_input.setFocus()

    def _on_new_code_entered(self, old_code: str, new_code: str, end_dt: int) -> None:
        """新卡片输入了兑换码"""
        if not new_code:
            return

        # 检查是否重复（包括 sample 和 user 配置）
        existing_codes = self.config.codes_dict
        if new_code in existing_codes:
            # 重复的兑换码，清空输入并提示（只清空发送信号的卡片）
            sender_card = self.sender()
            if sender_card and isinstance(sender_card, CodeCard):
                sender_card.code_input.clear()
                sender_card.code_input.setFocus()
            self._show_warning_toast(gt('兑换码已存在'))
            return

        # 保存到配置
        self.config.add_code(new_code, end_dt)

        # 将发送信号的卡片从"新卡片"转换为"已保存卡片"
        sender_card = self.sender()
        if sender_card and isinstance(sender_card, CodeCard):
            sender_card.is_new = False
            sender_card.original_code = new_code
            # 断开旧的信号连接，连接新的处理器
            sender_card.changed.disconnect(self._on_new_code_entered)
            sender_card.deleted.disconnect(self._on_new_card_deleted)
            sender_card.changed.connect(self._on_code_changed)
            sender_card.deleted.connect(self._on_code_deleted)

    def _on_new_card_deleted(self, code: str) -> None:
        """删除新创建的空卡片"""
        # 找到发送信号的卡片并删除
        sender_card = self.sender()
        if sender_card and sender_card in self.code_cards:
            self.code_cards.remove(sender_card)
            self.content_widget.layout().removeWidget(sender_card)
            sender_card.deleteLater()

    def _on_code_changed(self, old_code: str, new_code: str, end_dt: int) -> None:
        """兑换码或过期日期被修改"""
        sender_card = self.sender()

        # 如果只是修改了过期日期（code 没变），直接更新
        if old_code == new_code:
            self.config.update_code(old_code, new_code, end_dt)
            return

        # 检查新 code 是否与已有的冲突（排除自身）
        existing_codes = self.config.codes_dict
        if new_code in existing_codes:
            # 冲突，恢复原值并提示
            if sender_card and isinstance(sender_card, CodeCard):
                sender_card.code_input.setText(old_code)
            self._show_warning_toast(gt('兑换码已存在'))
            return

        # 更新成功，更新 original_code
        self.config.update_code(old_code, new_code, end_dt)
        if sender_card and isinstance(sender_card, CodeCard):
            sender_card.original_code = new_code

    def _on_code_deleted(self, code: str) -> None:
        """删除兑换码"""
        self.config.delete_code(code)
        self._refresh_code_cards()

    def _refresh_code_cards(self) -> None:
        """刷新兑换码卡片列表"""
        # 移除旧的卡片
        for card in self.code_cards:
            self.content_widget.layout().removeWidget(card)
            card.deleteLater()
        self.code_cards.clear()

        # 移除添加按钮（如果存在）
        if self.add_btn is not None:
            self.content_widget.layout().removeWidget(self.add_btn)

        # 添加 sample 配置的兑换码（只读）
        sample_codes = self.config.sample_codes_dict
        for code, end_dt in sample_codes.items():
            card = CodeCard(code=code, end_dt=end_dt, readonly=True, parent=self)
            self.code_cards.append(card)
            self.content_widget.add_widget(card)

        # 添加用户配置的兑换码（可编辑，排除 sample 中已有的）
        user_codes = self.config.user_codes_dict
        for code, end_dt in user_codes.items():
            if code in sample_codes:
                continue  # 跳过 sample 中已有的（避免重复）
            card = CodeCard(code=code, end_dt=end_dt, parent=self)
            card.changed.connect(self._on_code_changed)
            card.deleted.connect(self._on_code_deleted)
            self.code_cards.append(card)
            self.content_widget.add_widget(card)

        # 重新添加按钮
        if self.add_btn is not None:
            self.content_widget.add_widget(self.add_btn, stretch=1)

    def _show_warning_toast(self, message: str) -> None:
        """显示警告提示"""
        InfoBar.warning(
            title='',
            content=message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )
