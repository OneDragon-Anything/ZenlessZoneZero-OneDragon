from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, SettingCardGroup, PushButton, ComboBox

from one_dragon.base.config.basic_game_config import TypeInputWay, ScreenSizeEnum, FullScreenEnum, MonitorEnum
from one_dragon.base.controller.pc_button.ds4_button_controller import Ds4ButtonEnum
from one_dragon.base.controller.pc_button.xbox_button_controller import XboxButtonEnum
from one_dragon.utils import cmd_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.expand_setting_card_group import ExpandSettingCardGroup
from one_dragon_qt.widgets.setting_card.key_setting_card import KeySettingCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import DoubleSpinBoxSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.config.game_config import GamepadTypeEnum, GameKeyAction
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

        content_widget.add_widget(self._get_basic_group())
        content_widget.add_widget(self._get_key_settings_group())
        content_widget.add_stretch(1)

        return content_widget

    def _get_basic_group(self) -> QWidget:
        basic_group = SettingCardGroup(gt('游戏基础'))

        self.input_way_opt = ComboBoxSettingCard(icon=FluentIcon.CLIPPING_TOOL, title='输入方式',
                                                 options_enum=TypeInputWay)
        basic_group.addSettingCard(self.input_way_opt)

        self.hdr_btn_enable = PushButton(text=gt('启用 HDR'), icon=FluentIcon.SETTING, parent=self)
        self.hdr_btn_enable.clicked.connect(self._on_hdr_enable_clicked)
        self.hdr_btn_disable = PushButton(text=gt('禁用 HDR'), icon=FluentIcon.SETTING, parent=self)
        self.hdr_btn_disable.clicked.connect(self._on_hdr_disable_clicked)
        self.hdr_btn = MultiPushSettingCard(icon=FluentIcon.SETTING, title='切换 HDR 状态',
                                            content='仅影响手动启动游戏，一条龙启动游戏会自动禁用 HDR',
                                            btn_list=[self.hdr_btn_disable, self.hdr_btn_enable])
        basic_group.addSettingCard(self.hdr_btn)

        basic_group.addSettingCard(self._get_launch_argument_group())

        return basic_group

    def _get_launch_argument_group(self) -> QWidget:
        launch_argument_group = ExpandSettingCardGroup(icon=FluentIcon.SETTING, title='启动参数')

        self.launch_argument_switch = SwitchSettingCard(icon=FluentIcon.SETTING, title='启动参数')
        launch_argument_group.addHeaderWidget(self.launch_argument_switch.btn)

        self.screen_size_opt = ComboBoxSettingCard(icon=FluentIcon.FIT_PAGE, title='窗口尺寸', options_enum=ScreenSizeEnum)
        launch_argument_group.addSettingCard(self.screen_size_opt)

        self.full_screen_opt = ComboBoxSettingCard(icon=FluentIcon.FULL_SCREEN, title='全屏', options_enum=FullScreenEnum)
        launch_argument_group.addSettingCard(self.full_screen_opt)

        self.popup_window_switch = SwitchSettingCard(icon=FluentIcon.LAYOUT, title='无边框窗口')
        launch_argument_group.addSettingCard(self.popup_window_switch)

        self.monitor_opt = ComboBoxSettingCard(icon=FluentIcon.COPY, title='显示器序号', options_enum=MonitorEnum)
        launch_argument_group.addSettingCard(self.monitor_opt)

        self.launch_argument_advance = TextSettingCard(
            icon=FluentIcon.COMMAND_PROMPT,
            title='高级参数',
            input_placeholder='如果你不知道这是做什么的 请不要填写'
        )
        launch_argument_group.addSettingCard(self.launch_argument_advance)

        return launch_argument_group

    def _get_key_settings_group(self) -> QWidget:
        key_settings_group = SettingCardGroup(gt('按键设置'))

        self.control_method_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='操控方式',
                                                      content='需使用手柄时，需先安装虚拟手柄依赖。',
                                                      options_enum=GamepadTypeEnum)
        key_settings_group.addSettingCard(self.control_method_opt)

        self._keyboard_group = self._get_keyboard_group()
        self._gamepad_group = self._get_gamepad_group()
        key_settings_group.addSettingCard(self._keyboard_group)
        key_settings_group.addSettingCard(self._gamepad_group)

        self.control_method_opt.value_changed.connect(self._on_control_method_changed)

        return key_settings_group

    def _get_keyboard_group(self) -> ExpandSettingCardGroup:
        key_group = ExpandSettingCardGroup(icon=FluentIcon.GAME, title='键盘按键')

        self._key_cards: dict[GameKeyAction, KeySettingCard] = {}
        for action in GameKeyAction:
            card = KeySettingCard(icon=FluentIcon.GAME, title=action.value.label)
            key_group.addSettingCard(card)
            self._key_cards[action] = card

        return key_group

    def _get_gamepad_group(self) -> ExpandSettingCardGroup:
        gamepad_group = ExpandSettingCardGroup(icon=FluentIcon.GAME, title='手柄按键')

        self.gamepad_display_combo = ComboBox()
        self.gamepad_display_combo.addItem('Xbox', userData=GamepadTypeEnum.XBOX.value.value)
        self.gamepad_display_combo.addItem('DS4', userData=GamepadTypeEnum.DS4.value.value)
        self.gamepad_display_combo.currentIndexChanged.connect(self._toggle_gamepad_cards)
        gamepad_group.addHeaderWidget(self.gamepad_display_combo)

        # xbox
        self.xbox_key_press_time_opt = DoubleSpinBoxSettingCard(icon=FluentIcon.GAME, title='单次按键持续时间(秒)',
                                                                content='自行调整，过小可能按键被吞，过大可能影响操作')
        gamepad_group.addSettingCard(self.xbox_key_press_time_opt)

        self._xbox_cards: dict[GameKeyAction, ComboBoxSettingCard] = {}
        for action in GameKeyAction:
            card = ComboBoxSettingCard(icon=FluentIcon.GAME, title=action.value.label, options_enum=XboxButtonEnum)
            gamepad_group.addSettingCard(card)
            self._xbox_cards[action] = card

        # ds4
        self.ds4_key_press_time_opt = DoubleSpinBoxSettingCard(icon=FluentIcon.GAME, title='单次按键持续时间(秒)',
                                                               content='自行调整，过小可能按键被吞，过大可能影响操作')
        gamepad_group.addSettingCard(self.ds4_key_press_time_opt)

        self._ds4_cards: dict[GameKeyAction, ComboBoxSettingCard] = {}
        for action in GameKeyAction:
            card = ComboBoxSettingCard(icon=FluentIcon.GAME, title=action.value.label, options_enum=Ds4ButtonEnum)
            gamepad_group.addSettingCard(card)
            self._ds4_cards[action] = card

        return gamepad_group

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.input_way_opt.init_with_adapter(self.ctx.game_config.type_input_way_adapter)

        self.launch_argument_switch.init_with_adapter(self.ctx.game_config.get_prop_adapter('launch_argument'))
        self.screen_size_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('screen_size'))
        self.full_screen_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('full_screen'))
        self.popup_window_switch.init_with_adapter(self.ctx.game_config.get_prop_adapter('popup_window'))
        self.monitor_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('monitor'))
        self.launch_argument_advance.init_with_adapter(self.ctx.game_config.get_prop_adapter('launch_argument_advance'))

        self.control_method_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('gamepad_type'))

        for action, card in self._key_cards.items():
            card.init_with_adapter(self.ctx.game_config.get_prop_adapter(f'key_{action.value.value}'))

        self.xbox_key_press_time_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_press_time'))
        for action, card in self._xbox_cards.items():
            card.init_with_adapter(self.ctx.game_config.get_prop_adapter(f'xbox_key_{action.value.value}'))

        self.ds4_key_press_time_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_press_time'))
        for action, card in self._ds4_cards.items():
            card.init_with_adapter(self.ctx.game_config.get_prop_adapter(f'ds4_key_{action.value.value}'))

        self._on_control_method_changed(-1, self.ctx.game_config.gamepad_type)

    def _on_control_method_changed(self, _index: int, value: object) -> None:
        """根据操控方式自动展开/收起键盘和手柄组，并同步手柄显示"""
        is_keyboard = value == GamepadTypeEnum.NONE.value.value
        if is_keyboard:
            self._keyboard_group.setExpand(True)
            self._gamepad_group.setExpand(False)
        else:
            self._keyboard_group.setExpand(False)
            self._gamepad_group.setExpand(True)

        # 同步头部下拉框（blockSignals 避免触发 _toggle_gamepad_cards 重复刷新）
        self.gamepad_display_combo.blockSignals(True)
        if value == GamepadTypeEnum.DS4.value.value:
            self.gamepad_display_combo.setCurrentIndex(1)
        else:
            self.gamepad_display_combo.setCurrentIndex(0)
        self.gamepad_display_combo.blockSignals(False)

        self._toggle_gamepad_cards()

    def _toggle_gamepad_cards(self) -> None:
        """根据头部下拉框切换 Xbox/DS4 卡片可见性"""
        is_xbox = self.gamepad_display_combo.currentData() == GamepadTypeEnum.XBOX.value.value

        self.xbox_key_press_time_opt.setVisible(is_xbox)
        for card in self._xbox_cards.values():
            card.setVisible(is_xbox)

        self.ds4_key_press_time_opt.setVisible(not is_xbox)
        for card in self._ds4_cards.values():
            card.setVisible(not is_xbox)

    def _on_hdr_enable_clicked(self) -> None:
        self.hdr_btn_enable.setEnabled(False)
        self.hdr_btn_disable.setEnabled(True)
        cmd_utils.run_command(['reg', 'add', 'HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences',
                               '/v', self.ctx.game_account_config.game_path, '/d', 'AutoHDREnable=2097;', '/f'])

    def _on_hdr_disable_clicked(self) -> None:
        self.hdr_btn_disable.setEnabled(False)
        self.hdr_btn_enable.setEnabled(True)
        cmd_utils.run_command(['reg', 'add', 'HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences',
                               '/v', self.ctx.game_account_config.game_path, '/d', 'AutoHDREnable=2096;', '/f'])
