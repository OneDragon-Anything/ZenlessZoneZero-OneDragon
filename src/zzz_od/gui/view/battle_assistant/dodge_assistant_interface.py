import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, ToolButton

from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import (
    DoubleSpinBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.battle_assistant.auto_battle.auto_battle_app import (
    AutoBattleApp,
)
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_config_file_path,
    get_auto_battle_op_config_list,
)
from zzz_od.application.battle_assistant.dodge_assitant import dodge_assistant_const
from zzz_od.config.game_config import GamepadTypeEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.battle_assistant.battle_state_display import BattleStateDisplay


class DodgeAssistantInterface(AppRunInterface):

    auto_op_loaded_signal = Signal()

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=dodge_assistant_const.APP_ID,
            object_name='dodge_assistant_interface',
            nav_text_cn='闪避助手',
            nav_icon=FluentIcon.GAME,
            parent=parent,
        )

        self.auto_op_loaded_signal.connect(self._on_auto_op_loaded_signal)

    def get_widget_at_top(self) -> QWidget:
        top_widget = Column()

        self.help_opt = HelpCard(url='https://one-dragon.com/zzz/zh/docs/feat_battle_assistant.html')
        top_widget.add_widget(self.help_opt)

        self.dodge_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='闪避方式')
        top_widget.add_widget(self.dodge_opt)

        self.del_btn = ToolButton(FluentIcon.DELETE)
        self.dodge_opt.hBoxLayout.addWidget(self.del_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.dodge_opt.hBoxLayout.addSpacing(16)
        self.del_btn.clicked.connect(self._on_del_clicked)

        self.gpu_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='GPU运算')
        top_widget.add_widget(self.gpu_opt)

        self.screenshot_interval_opt = DoubleSpinBoxSettingCard(
            icon=FluentIcon.GAME, title='截图间隔(秒)',
            content='游戏画面掉帧的话 可以适当加大截图间隔'
        )
        top_widget.add_widget(self.screenshot_interval_opt)

        self.gamepad_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='手柄类型',
            content='需先安装虚拟手柄依赖，参考文档或使用安装器。仅在战斗助手生效。',
            options_enum=GamepadTypeEnum
        )
        self.gamepad_type_opt.value_changed.connect(self._on_gamepad_type_changed)
        top_widget.add_widget(self.gamepad_type_opt)

        return top_widget

    def get_content_widget(self) -> QWidget:
        content_widget = QWidget()
        # 创建 QVBoxLayout 作为主布局
        main_layout = QVBoxLayout(content_widget)

        # 创建 QHBoxLayout 作为中间布局
        horizontal_layout = QHBoxLayout()

        # 将 QVBoxLayouts 加入 QHBoxLayout
        left_layout = QVBoxLayout()
        left_layout.addWidget(AppRunInterface.get_content_widget(self))

        right_layout = QVBoxLayout()
        self.battle_state_display = BattleStateDisplay(self.ctx)
        right_layout.addWidget(self.battle_state_display)

        horizontal_layout.addLayout(left_layout, stretch=1)
        horizontal_layout.addLayout(right_layout, stretch=1)

        # 设置伸缩因子，让 QHBoxLayout 占据空间
        main_layout.addLayout(horizontal_layout, stretch=1)

        return content_widget

    def on_interface_shown(self) -> None:
        """
        界面显示时 进行初始化
        :return:
        """
        AppRunInterface.on_interface_shown(self)
        self._update_dodge_way_opts()
        self.dodge_opt.init_with_adapter(self.ctx.battle_assistant_config.get_prop_adapter('dodge_assistant_config'))
        self.gpu_opt.init_with_adapter(self.ctx.model_config.get_prop_adapter('flash_classifier_gpu'))
        self.screenshot_interval_opt.init_with_adapter(self.ctx.battle_assistant_config.get_prop_adapter('screenshot_interval'))
        self.gamepad_type_opt.setValue(self.ctx.battle_assistant_config.gamepad_type)
        self.ctx.listen_event(AutoBattleApp.EVENT_OP_LOADED, self._on_auto_op_loaded_event)

        # # 调试用
        # from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
        # auto_op = AutoBattleOperator(self.ctx.auto_battle_context, 'auto_battle', '专属配队-简')
        # auto_op.init_before_running()
        # auto_op.start_running_async()
        # self._on_auto_op_loaded_event(ContextEventItem('', auto_op))

    def on_interface_hidden(self) -> None:
        AppRunInterface.on_interface_hidden(self)
        self.ctx.unlisten_all_event(self)
        self.battle_state_display.set_update_display(False)

    def _update_dodge_way_opts(self) -> None:
        """
        更新闪避指令
        :return:
        """
        self.dodge_opt.set_options_by_list(get_auto_battle_op_config_list('dodge'))

    def _on_del_clicked(self) -> None:
        """
        删除配置
        :return:
        """
        item: str = self.dodge_opt.getValue()
        if item is None:
            return

        path = get_auto_battle_config_file_path('dodge', item)
        if os.path.exists(path):
            os.remove(path)

        self._update_dodge_way_opts()

    def _on_gamepad_type_changed(self, idx: int, value: str) -> None:
        self.ctx.battle_assistant_config.gamepad_type = value

    def on_context_state_changed(self) -> None:
        """
        按运行状态更新显示
        :return:
        """
        AppRunInterface.on_context_state_changed(self)

        if self.battle_state_display is not None:
            self.battle_state_display.set_update_display(self.ctx.run_context.is_context_running)

    def _on_auto_op_loaded_event(self, event: ContextEventItem) -> None:
        """
        自动战斗指令加载之后
        :param event:
        :return:
        """
        if self.battle_state_display is None:
            return
        self.auto_op_loaded_signal.emit()

    def _on_auto_op_loaded_signal(self) -> None:
        """
        指令加载之后 更新需要监听的事件
        :return:
        """
        if self.battle_state_display is None:
            return
        self.battle_state_display.set_update_display(True)
