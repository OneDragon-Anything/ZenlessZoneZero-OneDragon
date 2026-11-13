from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, SettingCardGroup

from one_dragon.base.config.basic_game_config import TypeInputWay
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.expand_setting_card_group import (
    ExpandSettingCardGroup,
)
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.key_setting_card import KeySettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.config.game_config import GameKeyAction
from zzz_od.context.zzz_context import ZContext


class SettingGameInterface(VerticalScrollInterface):

    def __init__(self, ctx: ZContext, parent=None):
        self.ctx: ZContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='setting_game_interface',
            content_widget=None, parent=parent,
            nav_text_cn='游戏设置'
        )
        self.ctx: ZContext = ctx

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.help_opt = HelpCard(
            url='https://one-dragon.com/zzz/zh/setting/setting_game.html',
            title='设置说明',
            content='游戏路径、输入方式等基础设置，建议首次使用前检查一遍',
        )
        content_widget.add_widget(self.help_opt)

        content_widget.add_widget(self._get_basic_group())
        content_widget.add_widget(self._get_key_settings_group())
        content_widget.add_stretch(1)

        return content_widget

    def _get_basic_group(self) -> QWidget:
        basic_group = SettingCardGroup(gt('游戏基础'))

        self.input_way_opt = ComboBoxSettingCard(icon=FluentIcon.CLIPPING_TOOL, title='输入方式',
                                                 options_enum=TypeInputWay)
        basic_group.addSettingCard(self.input_way_opt)

        return basic_group

    def _get_key_settings_group(self) -> QWidget:
        key_settings_group = SettingCardGroup(gt('按键设置'))

        key_settings_group.addSettingCard(self._get_keyboard_group())

        return key_settings_group

    def _get_keyboard_group(self) -> ExpandSettingCardGroup:
        key_group = ExpandSettingCardGroup(icon=FluentIcon.GAME, title='键盘按键')

        self._key_cards: dict[GameKeyAction, KeySettingCard] = {}
        for action in GameKeyAction:
            card = KeySettingCard(icon=FluentIcon.GAME, title=action.value.label)
            key_group.addSettingCard(card)
            self._key_cards[action] = card

        return key_group

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.input_way_opt.init_with_adapter(self.ctx.game_config.type_input_way_adapter)

        for action, card in self._key_cards.items():
            card.init_with_adapter(self.ctx.game_config.get_prop_adapter(f'key_{action.value.value}'))
