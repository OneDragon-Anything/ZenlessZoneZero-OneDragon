from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.application.coffee import coffee_app_const
from zzz_od.application.coffee.coffee_config import (
    CoffeeCardNumEnum,
    CoffeeChallengeWay,
    CoffeeChooseWay,
)
from zzz_od.gui.dialog.app_setting_dialog import AppSettingDialog

if TYPE_CHECKING:
    from zzz_od.context.zzz_context import ZContext


class CoffeeSettingDialog(AppSettingDialog):

    def __init__(self, ctx: ZContext, parent: QWidget | None = None):
        super().__init__(ctx=ctx, title="咖啡店配置", parent=parent)

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.choose_way_opt = ComboBoxSettingCard(icon=FluentIcon.CALENDAR, title='咖啡选择', options_enum=CoffeeChooseWay)
        content_widget.add_widget(self.choose_way_opt)

        self.challenge_way_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='喝后挑战', options_enum=CoffeeChallengeWay)
        content_widget.add_widget(self.challenge_way_opt)

        self.card_num_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='体力计划外的数量', options_enum=CoffeeCardNumEnum)
        content_widget.add_widget(self.card_num_opt)

        self.predefined_team_opt = ComboBoxSettingCard(icon=FluentIcon.PEOPLE, title='预备编队')
        self.predefined_team_opt.value_changed.connect(self.on_predefined_team_changed)
        content_widget.add_widget(self.predefined_team_opt)

        self.auto_battle_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='自动战斗')
        content_widget.add_widget(self.auto_battle_opt)

        self.run_charge_plan_afterwards_opt = SwitchSettingCard(
            icon=FluentIcon.CALENDAR, title='结束后运行体力计划', content='咖啡店在体力计划后运行可开启'
        )
        content_widget.add_widget(self.run_charge_plan_afterwards_opt)

        content_widget.add_stretch(1)

        return content_widget

    def on_dialog_shown(self) -> None:
        super().on_dialog_shown()

        self.config = self.ctx.run_context.get_config(
            app_id=coffee_app_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )

        self.choose_way_opt.init_with_adapter(get_prop_adapter(self.config, 'choose_way'))
        self.challenge_way_opt.init_with_adapter(get_prop_adapter(self.config, 'challenge_way'))
        self.card_num_opt.init_with_adapter(get_prop_adapter(self.config, 'card_num'))

        config_list = ([ConfigItem('游戏内配队', -1)] +
                       [ConfigItem(team.name, team.idx) for team in self.ctx.team_config.team_list])
        self.predefined_team_opt.set_options_by_list(config_list)
        self.predefined_team_opt.init_with_adapter(get_prop_adapter(self.config, 'predefined_team_idx'))

        self.auto_battle_opt.set_options_by_list(get_auto_battle_op_config_list('auto_battle'))
        self.auto_battle_opt.init_with_adapter(get_prop_adapter(self.config, 'auto_battle'))
        team_idx = self.predefined_team_opt.combo_box.currentData()
        self.auto_battle_opt.setVisible(team_idx == -1)

        self.run_charge_plan_afterwards_opt.init_with_adapter(get_prop_adapter(self.config, 'run_charge_plan_afterwards'))

    def on_predefined_team_changed(self, idx: int, value: str) -> None:
        team_idx = self.predefined_team_opt.combo_box.currentData()
        self.auto_battle_opt.setVisible(team_idx == -1)
