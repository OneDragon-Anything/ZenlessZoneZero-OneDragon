from typing import Optional

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, SettingCardGroup

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.editable_combo_box_setting_card import (
    EditableComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.drive_disc_dismantle import drive_disc_dismantle_const
from zzz_od.application.drive_disc_dismantle.drive_disc_dismantle_config import (
    DismantleLevelEnum,
    DriveDiscDismantleConfig,
)
from zzz_od.application.random_play.random_play_config import (
    RANDOM_AGENT_NAME,
    RandomPlayConfig,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import AgentEnum


class ZOneDragonSettingInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        VerticalScrollInterface.__init__(
            self,
            object_name='zzz_one_dragon_setting_interface',
            content_widget=None, parent=parent,
            nav_text_cn='其他设置'
        )
        self.ctx: ZContext = ctx
        self.group_id: str = 'one_dragon'  # 当前打开页面的group_id

        self.random_play_config: Optional[RandomPlayConfig] = None
        self.drive_disc_dismantle_config: Optional[DriveDiscDismantleConfig] = None

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        content_widget.add_widget(self.get_random_play_group())
        content_widget.add_widget(self.get_drive_disc_dismantle_group())
        content_widget.add_stretch(1)

        return content_widget

    def get_random_play_group(self) -> QWidget:
        group = SettingCardGroup(gt('影像店'))

        agents_list = [ConfigItem(RANDOM_AGENT_NAME)] + [
                ConfigItem(agent_enum.value.agent_name)
                for agent_enum in AgentEnum
            ]
        self.random_play_agent_1 = EditableComboBoxSettingCard(
            icon=FluentIcon.PEOPLE, title=gt('影像店代理人-1'),
            options_list=agents_list,
        )
        self.random_play_agent_1.combo_box.setFixedWidth(110)
        group.addSettingCard(self.random_play_agent_1)

        self.random_play_agent_2 = EditableComboBoxSettingCard(
            icon=FluentIcon.PEOPLE, title=gt('影像店代理人-2'),
            options_list=agents_list,
        )
        self.random_play_agent_2.combo_box.setFixedWidth(110)
        group.addSettingCard(self.random_play_agent_2)

        return group

    def get_drive_disc_dismantle_group(self) -> QWidget:
        group = SettingCardGroup(gt('驱动盘拆解'))

        self.drive_disc_dismantle_level_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='驱动盘拆解等级',
                                                           options_enum=DismantleLevelEnum)
        group.addSettingCard(self.drive_disc_dismantle_level_opt)

        self.drive_disc_dismantle_abandon_opt = SwitchSettingCard(icon=FluentIcon.GAME, title='全部已弃置')
        group.addSettingCard(self.drive_disc_dismantle_abandon_opt)

        return group

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.random_play_config = self.ctx.run_context.get_config(
            app_id='random_play',
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.random_play_agent_1.init_with_adapter(get_prop_adapter(self.random_play_config, 'agent_name_1'))
        self.random_play_agent_2.init_with_adapter(get_prop_adapter(self.random_play_config, 'agent_name_2'))

        self.drive_disc_dismantle_config = self.ctx.run_context.get_config(
            app_id=drive_disc_dismantle_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.drive_disc_dismantle_level_opt.init_with_adapter(get_prop_adapter(self.drive_disc_dismantle_config, 'dismantle_level'))
        self.drive_disc_dismantle_abandon_opt.init_with_adapter(get_prop_adapter(self.drive_disc_dismantle_config, 'dismantle_abandon'))
