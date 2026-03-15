from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon

from one_dragon.base.operation.application import application_const
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.key_setting_card import KeySettingCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import (
    DoubleSpinBoxSettingCard,
)
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.application.commission_assistant import commission_assistant_const
from zzz_od.application.commission_assistant.commission_assistant_config import (
    CommissionAssistantConfig,
    DialogOptionEnum,
    StoryMode,
)
from zzz_od.application.zzz_application import ZApplication
from zzz_od.context.zzz_context import ZContext


class CommissionAssistantRunInterface(AppRunInterface):

    def __init__(self,
                 ctx: ZContext,
                 parent=None):
        self.ctx: ZContext = ctx
        self.app: Optional[ZApplication] = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            app_id=commission_assistant_const.APP_ID,
            object_name='commission_assistant_run_interface',
            nav_text_cn='委托助手',
            parent=parent,
        )
        self.config: Optional[CommissionAssistantConfig] = None

    def get_widget_at_top(self) -> QWidget:
        content = Row()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        content.h_layout.addLayout(left_layout)
        content.h_layout.addLayout(right_layout)

        self.help_opt = HelpCard(url='https://one-dragon.com/zzz/zh/docs/feat_game_assistant.html#_1-%E5%A7%94%E6%89%98%E5%8A%A9%E6%89%8B')
        left_layout.addWidget(self.help_opt)

        self.dialog_option_opt = ComboBoxSettingCard(
            icon=FluentIcon.CHAT,
            title='对话选项优先级',
            options_enum=DialogOptionEnum,
        )
        right_layout.addWidget(self.dialog_option_opt)

        self.dialog_click_interval_opt = DoubleSpinBoxSettingCard(icon=FluentIcon.DATE_TIME, title='对话点击间隔(秒)')
        self.dialog_click_interval_opt.spin_box.setSingleStep(0.05)
        left_layout.addWidget(self.dialog_click_interval_opt)

        self.story_mode_opt = ComboBoxSettingCard(icon=FluentIcon.PLAY, title='剧情模式', options_enum=StoryMode)
        right_layout.addWidget(self.story_mode_opt)

        self.dodge_config_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='自动闪避')
        left_layout.addWidget(self.dodge_config_opt)

        self.dodge_switch_opt = KeySettingCard(icon=FluentIcon.GAME, title='自动闪避开关', content='按键后，进入/退出自动闪避')
        right_layout.addWidget(self.dodge_switch_opt)

        self.auto_battle_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='自动战斗')
        left_layout.addWidget(self.auto_battle_opt)

        self.auto_battle_switch_opt = KeySettingCard(icon=FluentIcon.GAME, title='自动战斗开关', content='按键后，进入/退出自动战斗')
        right_layout.addWidget(self.auto_battle_switch_opt)

        return content

    def on_interface_shown(self) -> None:
        AppRunInterface.on_interface_shown(self)
        self.config = self.ctx.run_context.get_config(
            app_id=commission_assistant_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=application_const.DEFAULT_GROUP_ID,
        )

        self.dialog_click_interval_opt.init_with_adapter(get_prop_adapter(self.config, 'dialog_click_interval'))
        self.dialog_option_opt.init_with_adapter(get_prop_adapter(self.config, 'dialog_option'))
        self.story_mode_opt.init_with_adapter(get_prop_adapter(self.config, 'story_mode'))

        self.dodge_config_opt.set_options_by_list(get_auto_battle_op_config_list('dodge'))
        self.dodge_config_opt.init_with_adapter(get_prop_adapter(self.config, 'dodge_config'))
        self.dodge_switch_opt.init_with_adapter(get_prop_adapter(self.config, 'dodge_switch'))

        self.auto_battle_opt.set_options_by_list(get_auto_battle_op_config_list('auto_battle'))
        self.auto_battle_opt.init_with_adapter(get_prop_adapter(self.config, 'auto_battle'))
        self.auto_battle_switch_opt.init_with_adapter(get_prop_adapter(self.config, 'auto_battle_switch'))

    def on_interface_hidden(self) -> None:
        AppRunInterface.on_interface_hidden(self)
