from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import FluentIcon, HyperlinkCard
from typing import Optional

from one_dragon.base.operation.application_base import Application
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.key_setting_card import KeySettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.view.app_run_interface import AppRunInterface
from zzz_od.application.battle_assistant.auto_battle_config import get_auto_battle_op_config_list
from zzz_od.application.commission_assistant.commission_assistant_app import CommissionAssistantApp
from zzz_od.application.commission_assistant.commission_assistant_config import DialogOptionEnum, StoryMode
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
            object_name='commission_assistant_run_interface',
            nav_text_cn='委托助手',
            parent=parent,
        )

    def get_widget_at_top(self) -> QWidget:
        content = Row()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        content.h_layout.addLayout(left_layout)
        content.h_layout.addLayout(right_layout)

        self.help_opt = HyperlinkCard(icon=FluentIcon.HELP, title='使用说明', text='前往',
                                      url='https://onedragon-anything.github.io/zzz/zh/docs/feat_game_assistant.html#_1-%E5%A7%94%E6%89%98%E5%8A%A9%E6%89%8B')
        self.help_opt.setContent('先看说明 再使用与提问')
        left_layout.addWidget(self.help_opt)

        self.dialog_option_opt = ComboBoxSettingCard(
            icon=FluentIcon.CHAT,
            title='对话选项优先级',
            options_enum=DialogOptionEnum,
        )
        right_layout.addWidget(self.dialog_option_opt)

        self.dialog_click_interval_opt = TextSettingCard(
            icon=FluentIcon.DATE_TIME,  # 选择与时间相关的图标
            title='对话点击间隔（秒）',
        )
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

        self.dialog_click_interval_opt.init_with_adapter(self.ctx.commission_assistant_config.get_prop_adapter('dialog_click_interval', getter_convert='str', setter_convert='float'))
        self.dialog_option_opt.init_with_adapter(self.ctx.commission_assistant_config.get_prop_adapter('dialog_option'))
        self.story_mode_opt.init_with_adapter(self.ctx.commission_assistant_config.get_prop_adapter('story_mode'))

        self.dodge_config_opt.set_options_by_list(get_auto_battle_op_config_list('dodge'))
        self.dodge_config_opt.init_with_adapter(self.ctx.commission_assistant_config.get_prop_adapter('dodge_config'))
        self.dodge_switch_opt.init_with_adapter(self.ctx.commission_assistant_config.get_prop_adapter('dodge_switch'))

        self.auto_battle_opt.set_options_by_list(get_auto_battle_op_config_list('auto_battle'))
        self.auto_battle_opt.init_with_adapter(self.ctx.commission_assistant_config.get_prop_adapter('auto_battle'))
        self.auto_battle_switch_opt.init_with_adapter(self.ctx.commission_assistant_config.get_prop_adapter('auto_battle_switch'))

    def on_interface_hidden(self) -> None:
        AppRunInterface.on_interface_hidden(self)

    def get_app(self) -> Application:
        return CommissionAssistantApp(self.ctx)
