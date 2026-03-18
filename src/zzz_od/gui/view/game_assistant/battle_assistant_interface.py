from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon

from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon_qt.widgets.base_interface import BaseInterface
from zzz_od.application.game_assistant.auto_battle.auto_battle_app import AutoBattleApp
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.game_assistant.auto_battle_interface import AutoBattleInterface
from zzz_od.gui.view.game_assistant.battle_state_display import BattleStateDisplay, TaskDisplay
from zzz_od.gui.view.game_assistant.battle_assistant_run_interface import (
    BattleAssistantRunInterface,
)
from zzz_od.gui.view.game_assistant.dodge_assistant_interface import DodgeAssistantInterface


class BattleAssistantInterface(BaseInterface):
    """战斗助手界面，合并自动战斗和闪避助手"""

    auto_op_loaded_signal = Signal()

    MODE_AUTO_BATTLE = BattleAssistantRunInterface.MODE_AUTO_BATTLE
    MODE_DODGE_ASSISTANT = BattleAssistantRunInterface.MODE_DODGE_ASSISTANT

    def __init__(self, ctx: ZContext, parent=None):
        BaseInterface.__init__(
            self,
            object_name='battle_assistant_interface',
            nav_text_cn='战斗助手',
            nav_icon=FluentIcon.GAME,
            parent=parent,
        )
        self.ctx = ctx
        self.auto_op_loaded_signal.connect(self._on_auto_op_loaded_signal)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        init_mode = self.ctx.game_assistant_config.battle_mode
        if init_mode not in (self.MODE_AUTO_BATTLE, self.MODE_DODGE_ASSISTANT):
            init_mode = self.MODE_AUTO_BATTLE
            self.ctx.game_assistant_config.battle_mode = init_mode

        # 中间区域：左侧 StackedWidget + 右侧状态面板
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # 左侧 StackedWidget
        self.stacked_widget = QStackedWidget()
        self.auto_battle_interface = AutoBattleInterface(self.ctx)
        self.dodge_assistant_interface = DodgeAssistantInterface(self.ctx)
        self.auto_battle_interface.battle_mode_changed.connect(self._on_mode_changed)
        self.dodge_assistant_interface.battle_mode_changed.connect(self._on_mode_changed)
        self.stacked_widget.addWidget(self.auto_battle_interface)
        self.stacked_widget.addWidget(self.dodge_assistant_interface)
        self.stacked_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout.addWidget(self.stacked_widget, stretch=1)

        # 右侧状态面板（固定宽度，不额外扩展）
        right_widget = QWidget()
        right_widget.setMinimumWidth(350)
        right_widget.setMaximumWidth(400)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.task_display = TaskDisplay(self.ctx)
        right_layout.addWidget(self.task_display)
        self.battle_state_display = BattleStateDisplay(self.ctx)
        right_layout.addWidget(self.battle_state_display)
        content_layout.addWidget(right_widget, stretch=0)

        main_layout.addLayout(content_layout, stretch=1)
        self._apply_mode(init_mode)

    def _apply_mode(self, mode: str) -> None:
        if mode == self.MODE_AUTO_BATTLE:
            self.stacked_widget.setCurrentWidget(self.auto_battle_interface)
            self.task_display.setVisible(True)
            self.task_display.set_update_display(True)
        else:
            self.stacked_widget.setCurrentWidget(self.dodge_assistant_interface)
            self.task_display.setVisible(False)
            self.task_display.set_update_display(False)

        # 双页同步模式卡片值，避免来回切换后显示不一致
        self.auto_battle_interface.sync_battle_mode_card(mode)
        self.dodge_assistant_interface.sync_battle_mode_card(mode)

    def _on_mode_changed(self, value: str) -> None:
        """切换模式时更新 StackedWidget 和右侧面板"""
        if value not in (self.MODE_AUTO_BATTLE, self.MODE_DODGE_ASSISTANT):
            value = self.MODE_AUTO_BATTLE

        self.ctx.game_assistant_config.battle_mode = value

        current = self.stacked_widget.currentWidget()
        if current is not None and hasattr(current, 'on_interface_hidden'):
            current.on_interface_hidden()

        self._apply_mode(value)

        new_current = self.stacked_widget.currentWidget()
        if new_current is not None and hasattr(new_current, 'on_interface_shown'):
            new_current.on_interface_shown()

    def on_interface_shown(self) -> None:
        """界面显示时初始化当前活跃的子界面和状态面板"""
        mode = self.ctx.game_assistant_config.battle_mode
        if mode not in (self.MODE_AUTO_BATTLE, self.MODE_DODGE_ASSISTANT):
            mode = self.MODE_AUTO_BATTLE
            self.ctx.game_assistant_config.battle_mode = mode
        self._apply_mode(mode)

        current = self.stacked_widget.currentWidget()
        if current is not None and hasattr(current, 'on_interface_shown'):
            current.on_interface_shown()

        self.ctx.listen_event(AutoBattleApp.EVENT_OP_LOADED, self._on_auto_op_loaded_event)

    def on_interface_hidden(self) -> None:
        """界面隐藏时清理"""
        current = self.stacked_widget.currentWidget()
        if current is not None and hasattr(current, 'on_interface_hidden'):
            current.on_interface_hidden()

        self.ctx.unlisten_all_event(self)
        self.battle_state_display.set_update_display(False)
        self.task_display.set_update_display(False)

    def _on_auto_op_loaded_event(self, event: ContextEventItem) -> None:
        """自动战斗指令加载后，通过信号更新显示"""
        self.auto_op_loaded_signal.emit()

    def _on_auto_op_loaded_signal(self) -> None:
        """指令加载后更新状态显示"""
        self.battle_state_display.set_update_display(True)
        is_auto_battle = self.stacked_widget.currentWidget() == self.auto_battle_interface
        self.task_display.set_update_display(is_auto_battle)
