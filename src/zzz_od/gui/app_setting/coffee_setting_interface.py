from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.services.app_setting.app_setting_provider import GroupIdMixin
from one_dragon_qt.utils.config_utils import get_prop_adapter
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.expand_setting_card_group import (
    ExpandSettingCardGroup,
)
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.battle_assistant.auto_battle_config import (
    get_auto_battle_op_config_list,
)
from zzz_od.application.charge_plan.charge_plan_config import ChargePlanItem
from zzz_od.application.coffee import coffee_app_const
from zzz_od.application.coffee.coffee_config import (
    CoffeeCardNumEnum,
    CoffeeChallengeWay,
    CoffeeChooseWay,
    CoffeeConfig,
    CoffeeEndAction,
    CoffeeTransportPoint,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.gui.view.one_dragon.charge_plan_interface import DoubleRewardEventConfigCard


class CoffeeSettingInterface(VerticalScrollInterface, GroupIdMixin):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='zzz_coffee_plan_interface',
            content_widget=None, parent=parent,
            nav_text_cn='咖啡计划'
        )

        self.config: CoffeeConfig | None = None

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.transport_point_opt = ComboBoxSettingCard(icon=FluentIcon.SEND, title='传送地点', content='选择前往的咖啡店', options_enum=CoffeeTransportPoint)
        content_widget.add_widget(self.transport_point_opt)

        self.choose_way_opt = ComboBoxSettingCard(icon=FluentIcon.CALENDAR, title='咖啡选择', content='选择当天的咖啡匹配方式', options_enum=CoffeeChooseWay)
        content_widget.add_widget(self.choose_way_opt)

        self.challenge_group = ExpandSettingCardGroup(icon=FluentIcon.GAME, title='喝后挑战', content=CoffeeChallengeWay.ALL.value.desc)
        content_widget.add_widget(self.challenge_group)

        self.challenge_way_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='喝后挑战', options_enum=CoffeeChallengeWay)
        self.challenge_way_opt.value_changed.connect(self.on_challenge_way_changed)
        self.challenge_group.addHeaderWidget(self.challenge_way_opt.combo_box)

        self.card_num_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='体力计划外的数量', content='喝后挑战找不到对应体力计划配置时，使用这里设置的卡片数量', options_enum=CoffeeCardNumEnum)
        self.challenge_group.addSettingCard(self.card_num_opt)

        self.predefined_team_opt = ComboBoxSettingCard(icon=FluentIcon.PEOPLE, title='预备编队', content='选择喝后挑战使用的编队，游戏内配队会沿用当前队伍')
        self.predefined_team_opt.value_changed.connect(self.on_predefined_team_changed)
        self.challenge_group.addSettingCard(self.predefined_team_opt)

        self.auto_battle_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='自动战斗', content='仅选择游戏内配队时生效，其他预备编队使用各自的自动战斗配置')
        self.challenge_group.addSettingCard(self.auto_battle_opt)

        self.end_action_group = ExpandSettingCardGroup(icon=FluentIcon.CALENDAR, title='结束后处理', content=CoffeeEndAction.NONE.value.desc)
        content_widget.add_widget(self.end_action_group)

        self.end_action_opt = ComboBoxSettingCard(icon=FluentIcon.CALENDAR, title='结束后处理', options_enum=CoffeeEndAction)
        self.end_action_opt.value_changed.connect(self.on_end_action_changed)
        self.end_action_group.addHeaderWidget(self.end_action_opt.combo_box)

        self.fallback_plan_opt = DoubleRewardEventConfigCard(self.ctx, category_name='实战模拟室')
        self.fallback_plan_opt.titleLabel.setText('实战模拟室兜底计划')
        self.fallback_plan_opt.setContent('剩余20～39电量刷1张，40～59刷2张；不计入体力计划次数')
        self.fallback_plan_opt.changed.connect(self.set_fallback_plan)
        self.end_action_group.addSettingCard(self.fallback_plan_opt)

        for group in (self.challenge_group, self.end_action_group):
            group.setExpand(True)
            group.card.expandButton.setDisabled(True)
            group.card.expandButton.hide()

        content_widget.add_stretch(1)

        return content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.config = self.ctx.run_context.get_config(
            app_id=coffee_app_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )

        self.transport_point_opt.init_with_adapter(get_prop_adapter(self.config, 'transport_point'))
        self.choose_way_opt.init_with_adapter(get_prop_adapter(self.config, 'choose_way'))
        self.challenge_way_opt.init_with_adapter(get_prop_adapter(self.config, 'challenge_way'))
        self.card_num_opt.init_with_adapter(get_prop_adapter(self.config, 'card_num'))
        self.end_action_opt.init_with_adapter(get_prop_adapter(self.config, 'end_action'))
        self.fallback_plan_opt.init_with_plan(self.config.remaining_charge_fallback_plan)

        config_list = ([ConfigItem('游戏内配队', -1)] +
                       [ConfigItem(team.name, team.idx) for team in self.ctx.team_config.team_list])
        self.predefined_team_opt.set_options_by_list(config_list)
        self.predefined_team_opt.init_with_adapter(get_prop_adapter(self.config, 'predefined_team_idx'))

        self.auto_battle_opt.set_options_by_list(get_auto_battle_op_config_list('auto_battle'))
        self.auto_battle_opt.init_with_adapter(get_prop_adapter(self.config, 'auto_battle'))
        team_idx = self.predefined_team_opt.combo_box.currentData()
        self.auto_battle_opt.setVisible(team_idx == -1)

        self.on_challenge_way_changed(0, self.config.challenge_way)
        self.on_end_action_changed(0, self.config.end_action)

    def on_challenge_way_changed(self, idx: int, value: str) -> None:
        desc = next(item.value.desc for item in CoffeeChallengeWay if item.value.value == value)
        self.challenge_group.card.setContent(desc)
        challenge_enabled = value != CoffeeChallengeWay.NONE.value.value
        self.card_num_opt.setEnabled(value == CoffeeChallengeWay.ALL.value.value)
        self.predefined_team_opt.setEnabled(challenge_enabled)
        self.auto_battle_opt.setEnabled(challenge_enabled)

    def on_predefined_team_changed(self, idx: int, value: str) -> None:
        team_idx = self.predefined_team_opt.combo_box.currentData()
        self.auto_battle_opt.setVisible(team_idx == -1)

    def on_end_action_changed(self, idx: int, value: str) -> None:
        desc = next(item.value.desc for item in CoffeeEndAction if item.value.value == value)
        self.end_action_group.card.setContent(desc)
        self.fallback_plan_opt.setEnabled(value == CoffeeEndAction.RUN_CHARGE_PLAN_WITH_FALLBACK.value.value)

    def set_fallback_plan(self, plan: ChargePlanItem) -> None:
        if self.config is not None:
            self.config.remaining_charge_fallback_plan = plan
