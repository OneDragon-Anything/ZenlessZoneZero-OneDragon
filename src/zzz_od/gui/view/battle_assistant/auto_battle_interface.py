import os.path
from typing import Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, PushButton, ToolButton

from one_dragon.base.operation.context_event_bus import ContextEventItem
from one_dragon.utils.i18_utils import gt
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
from zzz_od.application.battle_assistant.auto_battle import auto_battle_const
from zzz_od.application.battle_assistant.auto_battle.auto_battle_app import (
    AutoBattleApp,
)
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_config_file_path,
    get_auto_battle_op_config_list,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.config.game_config import GamepadTypeEnum
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.battle_assistant.battle_state_display import (
    BattleStateDisplay,
    TaskDisplay,
)


class AutoBattleInterface(AppRunInterface):

    auto_op_loaded_signal = Signal()

    def __init__(self, ctx: ZContext, parent=None):
        """初始化 AutoBattleInterface 类"""
        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=auto_battle_const.APP_ID,
            object_name='auto_battle_interface',
            nav_text_cn='自动战斗',
            nav_icon=FluentIcon.GAME,
            parent=parent,
        )
        self.ctx: ZContext = ctx
        self.app: Optional[ZApplication] = None
        self.auto_op_loaded_signal.connect(self._on_auto_op_loaded_signal)

        if hasattr(ctx, 'telemetry') and ctx.telemetry:
            ctx.telemetry.track_ui_interaction('auto_battle_interface', 'view', {
                'interface_type': 'battle_assistant',
                'feature': 'auto_battle'
            })

    def get_widget_at_top(self) -> QWidget:
        top_widget = Column()

        self.help_opt = HelpCard(url='https://one-dragon.com/zzz/zh/docs/feat_battle_assistant.html')
        top_widget.add_widget(self.help_opt)

        self.config_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='战斗配置',
            content='调试为以当前画面做一次判断执行。配置文件在 config/auto_battle 文件夹，删除会恢复默认配置'
        )
        self.config_opt.hBoxLayout.addSpacing(16)
        self.shared_btn = PushButton(gt('前往社区'))
        self.shared_btn.clicked.connect(self._on_shared_clicked)
        self.config_opt.hBoxLayout.addWidget(self.shared_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.config_opt.hBoxLayout.addSpacing(16)
        self.del_btn = ToolButton(FluentIcon.DELETE)
        self.del_btn.clicked.connect(self._on_del_clicked)
        self.config_opt.hBoxLayout.addWidget(self.del_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.config_opt.hBoxLayout.addSpacing(16)
        top_widget.add_widget(self.config_opt)
        self.config_opt.value_changed.connect(self._on_auto_battle_config_changed)

        self.gpu_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='GPU运算', content='游戏画面掉帧的话 可以不启用')
        top_widget.add_widget(self.gpu_opt)

        self.screenshot_interval_opt = DoubleSpinBoxSettingCard(
            icon=FluentIcon.GAME, title='截图间隔(秒)',
            content='游戏画面掉帧的话 可以适当加大截图间隔(小心,太久会关不掉软件的)',
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

        self.task_display = TaskDisplay()
        right_layout.addWidget(self.task_display)

        self.battle_state_display = BattleStateDisplay()
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
        self._update_auto_battle_config_opts()
        self.config_opt.setValue(self.ctx.battle_assistant_config.auto_battle_config)
        self.gpu_opt.init_with_adapter(self.ctx.model_config.get_prop_adapter('flash_classifier_gpu'))
        self.screenshot_interval_opt.init_with_adapter(self.ctx.battle_assistant_config.get_prop_adapter('screenshot_interval'))
        self.gamepad_type_opt.setValue(self.ctx.battle_assistant_config.gamepad_type)
        self.ctx.listen_event(AutoBattleApp.EVENT_OP_LOADED, self._on_auto_op_loaded_event)

    def on_interface_hidden(self) -> None:
        AppRunInterface.on_interface_hidden(self)
        self.ctx.unlisten_all_event(self)
        self.battle_state_display.set_update_display(False)
        self.task_display.set_update_display(False)

    def _update_auto_battle_config_opts(self) -> None:
        """
        更新闪避指令
        :return:
        """
        self.config_opt.set_options_by_list(get_auto_battle_op_config_list('auto_battle'))

    def _on_auto_battle_config_changed(self, index, value):
        self.ctx.battle_assistant_config.auto_battle_config = value

        self.app = auto_battle_const.APP_ID
        AppRunInterface._on_start_clicked(self)

    def _on_shared_clicked(self) -> None:
        """
        打开配置共享频道
        """
        QDesktopServices.openUrl(QUrl("https://pd.qq.com/g/onedrag00n"))

        # """
        # 弹出列表, 此功能对接服务器已经消失, 暂时隐藏
        # """
        # dialog = SharedConfigDialog(self)
        # if dialog.exec():
        #     self._refresh_interface()
        # else:
        #     self._refresh_interface()


    def _on_del_clicked(self) -> None:
        """
        删除配置 只删除非 sample 的
        :return:
        """
        item: str = self.config_opt.getValue()
        if item is None:
            return

        path = get_auto_battle_config_file_path('auto_battle', item)
        if os.path.exists(path):
            os.remove(path)

        self._update_auto_battle_config_opts()

    def _on_gamepad_type_changed(self, idx: int, value: str) -> None:
        self.ctx.battle_assistant_config.gamepad_type = value

    def _on_key_press(self, event: ContextEventItem) -> None:
        """
        按键监听
        """
        key: str = event.data
        if key == self.ctx.key_start_running and self.ctx.run_context.is_context_stop:
            self._on_start_clicked()

    def on_context_state_changed(self) -> None:
        """
        按运行状态更新显示
        :return:
        """
        AppRunInterface.on_context_state_changed(self)

        if self.battle_state_display is not None:
            self.battle_state_display.set_update_display(self.ctx.run_context.is_context_running)
        if self.task_display is not None:
            self.task_display.set_update_display(self.ctx.run_context.is_context_running)

    def _on_auto_op_loaded_event(self, event: ContextEventItem) -> None:
        """
        自动战斗指令加载之后
        :param event:
        :return:
        """
        if self.battle_state_display is None or self.task_display is None:
            return
        self.battle_state_display.auto_op = event.data
        self.task_display.auto_op = event.data
        self.auto_op_loaded_signal.emit()

    def _on_auto_op_loaded_signal(self) -> None:
        """
        指令加载之后 更新需要监听的事件
        :return:
        """
        if self.battle_state_display is None or self.task_display is None:
            return
        self.battle_state_display.set_update_display(True)
        self.task_display.set_update_display(True)

    def _refresh_interface(self):
        """
        刷新界面
        """
        self._update_auto_battle_config_opts()
        self.config_opt.setValue(self.ctx.battle_assistant_config.auto_battle_config)
        self.gpu_opt.init_with_adapter(self.ctx.model_config.get_prop_adapter('flash_classifier_gpu'))
        self.screenshot_interval_opt.setValue(str(self.ctx.battle_assistant_config.screenshot_interval))
        self.gamepad_type_opt.setValue(self.ctx.battle_assistant_config.gamepad_type)
