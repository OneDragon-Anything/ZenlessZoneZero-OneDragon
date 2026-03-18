from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import FluentIcon, MessageBox, PushButton, SettingCard

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import (
    DoubleSpinBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.config.game_config import ControlMethodEnum
from zzz_od.context.zzz_context import ZContext


class BattleAssistantRunInterface(AppRunInterface):
    battle_mode_changed = Signal(str)

    MODE_AUTO_BATTLE = '自动战斗'
    MODE_DODGE_ASSISTANT = '闪避助手'

    def __init__(
        self,
        ctx: ZContext,
        app_id: str,
        object_name: str,
        nav_text_cn: str,
        nav_icon=FluentIcon.GAME,
        parent=None,
    ):
        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=app_id,
            object_name=object_name,
            nav_text_cn=nav_text_cn,
            nav_icon=nav_icon,
            parent=parent,
        )
        self.ctx: ZContext = ctx

        self.help_opt: SettingCard | None = None
        self.mode_opt: ComboBoxSettingCard | None = None
        self.gpu_opt: SwitchSettingCard | None = None
        self.screenshot_interval_opt: DoubleSpinBoxSettingCard | None = None
        self.gamepad_type_opt: ComboBoxSettingCard | None = None

    def _add_help_card(self, top_widget: Column) -> None:
        self.help_opt = SettingCard(FluentIcon.HELP, gt('使用说明'), gt('先看说明 再使用与提问'))
        self.help_opt.setFixedHeight(50)

        desc_btn = PushButton(gt('如何让AI打得更好？'))
        desc_btn.clicked.connect(self._on_desc_clicked)
        self.help_opt.hBoxLayout.addWidget(desc_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.help_opt.hBoxLayout.addSpacing(16)

        guide_btn = PushButton(gt('查看指南'))
        guide_btn.clicked.connect(self._on_help_clicked)
        self.help_opt.hBoxLayout.addWidget(guide_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.help_opt.hBoxLayout.addSpacing(16)

        shared_btn = PushButton(gt('前往社区'))
        shared_btn.clicked.connect(self._on_shared_clicked)
        self.help_opt.hBoxLayout.addWidget(shared_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.help_opt.hBoxLayout.addSpacing(16)

        top_widget.add_widget(self.help_opt)

    def _add_mode_card(self, top_widget: Column) -> None:
        self.mode_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title='战斗模式',
            content='选择自动战斗或闪避助手模式',
        )
        mode_options = [
            ConfigItem(label=self.MODE_AUTO_BATTLE),
            ConfigItem(label=self.MODE_DODGE_ASSISTANT),
        ]
        self.mode_opt.set_options_by_list(mode_options)
        init_mode = self.ctx.battle_assistant_config.battle_mode
        if init_mode not in (self.MODE_AUTO_BATTLE, self.MODE_DODGE_ASSISTANT):
            init_mode = self.MODE_AUTO_BATTLE
        self.mode_opt.setValue(init_mode)
        self.mode_opt.value_changed.connect(self._on_mode_changed)
        top_widget.add_widget(self.mode_opt)

    def _add_shared_common_cards(self, top_widget: Column) -> None:
        self.gpu_opt = SwitchSettingCard(
            icon=FluentIcon.GAME,
            title='GPU运算',
            content='游戏画面掉帧的话 可以不启用',
        )
        top_widget.add_widget(self.gpu_opt)

        self.screenshot_interval_opt = DoubleSpinBoxSettingCard(
            icon=FluentIcon.GAME,
            title='截图间隔 (秒)',
            content='一般默认0.02，除非电脑很卡。优先通过设置游戏30帧和低画质给AI留算力',
            minimum=0.02,
            maximum=0.1,
        )
        top_widget.add_widget(self.screenshot_interval_opt)

        self.gamepad_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title='操作方式',
            content='仅影响自动战斗。如需使用手柄，请先安装虚拟手柄依赖。',
            options_enum=ControlMethodEnum,
        )
        self.gamepad_type_opt.value_changed.connect(self._on_gamepad_type_changed)
        top_widget.add_widget(self.gamepad_type_opt)

    def _init_shared_common_cards(self) -> None:
        self.sync_battle_mode_card(self.ctx.battle_assistant_config.battle_mode)

        if self.gpu_opt is not None:
            self.gpu_opt.init_with_adapter(get_prop_adapter(self.ctx.model_config, 'flash_classifier_gpu'))
        if self.screenshot_interval_opt is not None:
            self.screenshot_interval_opt.init_with_adapter(
                get_prop_adapter(self.ctx.battle_assistant_config, 'screenshot_interval')
            )
        if self.gamepad_type_opt is not None:
            self.gamepad_type_opt.setValue(self.ctx.battle_assistant_config.control_method)

    def sync_battle_mode_card(self, mode: str) -> None:
        if self.mode_opt is None:
            return
        if mode not in (self.MODE_AUTO_BATTLE, self.MODE_DODGE_ASSISTANT):
            mode = self.MODE_AUTO_BATTLE
        if self.mode_opt.getValue() == mode:
            return

        self.mode_opt.blockSignals(True)
        self.mode_opt.setValue(mode)
        self.mode_opt.blockSignals(False)

    def _on_mode_changed(self, index: int, value: str) -> None:
        if value not in (self.MODE_AUTO_BATTLE, self.MODE_DODGE_ASSISTANT):
            value = self.MODE_AUTO_BATTLE
        self.battle_mode_changed.emit(value)

    def _on_gamepad_type_changed(self, idx: int, value: str) -> None:
        self.ctx.battle_assistant_config.control_method = value

    def _on_help_clicked(self) -> None:
        QDesktopServices.openUrl(QUrl("https://one-dragon.com/zzz/zh/feat_game_assistant.html"))

    def _on_shared_clicked(self) -> None:
        QDesktopServices.openUrl(QUrl("https://pd.qq.com/g/onedrag00n"))

    def _on_desc_clicked(self) -> None:
        content = "这是一条消息通知"
        try:
            file_path = Path(os_utils.get_path_under_work_dir('docs', 'game_assistant_notice.md'))
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8')
        except Exception:
            pass

        w = MessageBox(gt("使用说明"), content, self.window())
        w.cancelButton.hide()
        w.yesButton.setText(gt("确认"))
        w.exec()
