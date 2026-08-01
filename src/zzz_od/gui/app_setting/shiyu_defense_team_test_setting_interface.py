from functools import partial

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, SettingCardGroup

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.services.app_setting.app_setting_provider import GroupIdMixin
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.horizontal_setting_card_group import (
    HorizontalSettingCardGroup,
)
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.application.devtools.shiyu_defense_team_test import (
    shiyu_defense_team_test_const,
)
from zzz_od.application.devtools.shiyu_defense_team_test.shiyu_defense_team_test_config import (
    ShiyuDefenseTeamTestConfig,
)
from zzz_od.context.zzz_context import ZContext
from zzz_od.game_data.agent import DmgTypeEnum


class ShiyuDefenseTeamTestInterface(VerticalScrollInterface, GroupIdMixin):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx
        self.config: ShiyuDefenseTeamTestConfig | None = None
        self.target_group_list: list[SettingCardGroup] = []
        self.target_dmg_type_opt_map: dict[
            tuple[int, bool, int], ComboBoxSettingCard
        ] = {}

        VerticalScrollInterface.__init__(
            self,
            content_widget=None,
            object_name='shiyu_defense_team_test_setting_interface',
            nav_text_cn='配队选择',
            nav_icon=FluentIcon.PEOPLE,
            parent=parent,
        )

    def get_content_widget(self) -> QWidget:
        top_widget = Column()

        self.target_count_opt = ComboBoxSettingCard(
            icon=FluentIcon.PEOPLE,
            title='目标数量',
            content='先在游戏内打开预备编队选择页，再开始配队选择。',
            options_list=[
                ConfigItem('1', 1),
                ConfigItem('2', 2),
                ConfigItem('3', 3),
            ],
        )
        self.target_count_opt.value_changed.connect(self._on_target_count_changed)
        top_widget.add_widget(self.target_count_opt)

        dmg_type_options = [ConfigItem('无', '')] + [
            ConfigItem(dmg_type.value, dmg_type.name)
            for dmg_type in DmgTypeEnum
            if dmg_type != DmgTypeEnum.UNKNOWN
        ]
        for target_idx in range(3):
            target_group = SettingCardGroup(f'目标队伍 {target_idx + 1}')
            weakness_cards: list[ComboBoxSettingCard] = []
            resistance_cards: list[ComboBoxSettingCard] = []
            for is_weakness, cards in [
                (True, weakness_cards),
                (False, resistance_cards),
            ]:
                type_name = '弱点' if is_weakness else '抗性'
                for type_idx in range(2):
                    card = ComboBoxSettingCard(
                        icon=FluentIcon.FLAG,
                        title=f'{type_name} {type_idx + 1}',
                        options_list=dmg_type_options,
                    )
                    card.value_changed.connect(
                        partial(
                            self._on_target_dmg_type_changed,
                            target_idx,
                            is_weakness,
                            type_idx,
                        )
                    )
                    cards.append(card)
                    self.target_dmg_type_opt_map[
                        (target_idx, is_weakness, type_idx)
                    ] = card

            target_group.addSettingCard(
                HorizontalSettingCardGroup(weakness_cards, spacing=6)
            )
            target_group.addSettingCard(
                HorizontalSettingCardGroup(resistance_cards, spacing=6)
            )
            top_widget.add_widget(target_group)
            self.target_group_list.append(target_group)

        return top_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.config = self.ctx.run_context.get_config(
            app_id=shiyu_defense_team_test_const.APP_ID,
            instance_idx=self.ctx.current_instance_idx,
            group_id=self.group_id,
        )
        self.target_count_opt.setValue(self.config.target_count, emit_signal=False)
        for key, card in self.target_dmg_type_opt_map.items():
            target_idx, is_weakness, type_idx = key
            card.setValue(
                self.config.get_target_dmg_type(
                    target_idx,
                    is_weakness,
                    type_idx,
                ),
                emit_signal=False,
            )
        self._update_target_enabled()

    def _on_target_count_changed(self, _: int, value: int) -> None:
        if self.config is None:
            return
        self.config.target_count = value
        self._update_target_enabled()

    def _on_target_dmg_type_changed(
        self,
        target_idx: int,
        is_weakness: bool,
        type_idx: int,
        _: int,
        value: str,
    ) -> None:
        if self.config is None:
            return
        self.config.set_target_dmg_type(
            target_idx,
            is_weakness,
            type_idx,
            value,
        )

    def _update_target_enabled(self) -> None:
        target_count = self.target_count_opt.getValue()
        for target_idx, target_group in enumerate(self.target_group_list):
            target_group.setEnabled(target_idx < target_count)
