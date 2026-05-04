import os.path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, ToolButton

from one_dragon.base.operation.application import application_const
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.editable_combo_box_setting_card import (
    EditableComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_config_file_path,
)
from zzz_od.application.battle_assistant.operation_template_config import (
    get_operation_template_config_list,
)
from zzz_od.application.devtools.operation_debug import operation_debug_const
from zzz_od.application.devtools.operation_debug.operation_debug_config import (
    OperationDebugConfig,
)
from zzz_od.config.game_config import ControlMethodEnum
from zzz_od.context.zzz_context import ZContext


class OperationDebugInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.config: OperationDebugConfig | None = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=operation_debug_const.APP_ID,
            object_name='operation_debug_interface',
            nav_text_cn='指令调试',
            nav_icon=FluentIcon.GAME,
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        top_widget = Column()

        self.config_opt = EditableComboBoxSettingCard(
            icon=FluentIcon.GAME, title='指令配置',
            content='在 config/auto_battle_operation 文件夹')
        self.config_opt.value_changed.connect(self._on_config_changed)
        top_widget.add_widget(self.config_opt)

        self.del_btn = ToolButton(FluentIcon.DELETE)
        self.config_opt.hBoxLayout.addWidget(self.del_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.config_opt.hBoxLayout.addSpacing(16)
        self.del_btn.clicked.connect(self._on_del_clicked)

        self.repeat_opt = SwitchSettingCard(
            icon=FluentIcon.GAME, title='循环指令',
            content='不断重复指令 确保可以连贯执行'
        )
        self.repeat_opt.value_changed.connect(self._on_repeat_changed)
        top_widget.add_widget(self.repeat_opt)

        self.gamepad_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='操作方式',
            content='仅影响自动战斗。如需使用手柄，请先安装虚拟手柄依赖。',
            options_enum=ControlMethodEnum
        )
        self.gamepad_type_opt.value_changed.connect(self._on_gamepad_type_changed)
        top_widget.add_widget(self.gamepad_type_opt)

        return top_widget

    def on_interface_shown(self) -> None:
        """
        界面显示时 进行初始化
        :return:
        """
        AppRunInterface.on_interface_shown(self)
        self.config = self.ctx.run_context.get_config(
            app_id=operation_debug_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )
        self._update_auto_battle_config_opts()
        self.config_opt.setValue(self.config.operation_template)
        self.gamepad_type_opt.setValue(self.ctx.battle_assistant_config.control_method)
        self.repeat_opt.setValue(self.config.repeat_enabled)

    def _update_auto_battle_config_opts(self) -> None:
        """
        更新闪避指令，支持子目录中的模板文件
        :return:
        """
        self.config_opt.blockSignals(True)
        # 获取模板列表（包含子目录路径）
        config_list = get_operation_template_config_list()

        # 设置下拉选项
        self.config_opt.set_options_by_list(config_list)

        self.config_opt.blockSignals(False)

    def _on_config_changed(self, index, value):
        if self.config is not None:
            self.config.operation_template = value

    def _on_repeat_changed(self, value: bool) -> None:
        if self.config is not None:
            self.config.repeat_enabled = value

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
        self.ctx.battle_assistant_config.control_method = value
