from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from zzz_od.application.redemption_code import redemption_code_const
from zzz_od.application.redemption_code.redemption_code_config import RedemptionCodeConfig
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class RedemptionCodeSettingDialog(AppSettingDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="兑换码配置", parent=parent)

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        # 兑换码文本输入卡片
        self.codes_text_card = TextSettingCard(
            icon=FluentIcon.GAME,
            title='兑换码填写处',
            content='不同的兑换码请用空格分开',
            input_max_width=1000
        )

        # 设置占位符文本
        self.codes_text_card.line_edit.setPlaceholderText("ABC123 DEF456 GHI789")

        content_widget.add_widget(self.codes_text_card)
        content_widget.add_stretch(1)

        return content_widget

    def on_dialog_shown(self) -> None:
        super().on_dialog_shown()

        self.config: RedemptionCodeConfig = self.ctx.run_context.get_config(
            app_id=redemption_code_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )

        # 创建自定义适配器来处理兑换码文本的读写
        class CodesTextAdapter:
            def __init__(self, config: RedemptionCodeConfig):
                self.config = config

            def get_value(self) -> str:
                return self.config.get_codes_text()

            def set_value(self, value: str) -> None:
                self.config.update_codes_from_text(value)

        # 初始化适配器
        adapter = CodesTextAdapter(self.config)
        self.codes_text_card.init_with_adapter(adapter)

        # 启用实时保存：将默认的editingFinished信号改为textChanged信号
        self.codes_text_card.line_edit.editingFinished.disconnect()
        self.codes_text_card.line_edit.textChanged.connect(self.codes_text_card._on_text_changed)
