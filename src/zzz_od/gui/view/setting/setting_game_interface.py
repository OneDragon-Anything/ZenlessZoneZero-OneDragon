from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, InfoBar, PushButton, SettingCardGroup

from one_dragon.base.config.basic_game_config import (
    FullScreenEnum,
    MonitorEnum,
    ScreenSizeEnum,
    TypeInputWay,
)
from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.controller.pc_button.ds4_button_controller import Ds4ButtonEnum
from one_dragon.base.controller.pc_button.xbox_button_controller import XboxButtonEnum
from one_dragon.utils import cmd_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.expand_setting_card_group import (
    ExpandSettingCardGroup,
)
from one_dragon_qt.widgets.setting_card.gamepad_action_key_card import (
    GamepadActionKeyCard,
)
from one_dragon_qt.widgets.setting_card.key_setting_card import KeySettingCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.spin_box_setting_card import (
    DoubleSpinBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.config.game_config import (
    ControlMethodEnum,
    GameKeyAction,
    GamepadActionEnum,
    GamepadTypeEnum,
)
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

        basic_group.addSettingCard(self._get_background_mode_group())

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

    def _get_background_mode_group(self) -> ExpandSettingCardGroup:
        """后台模式开关 + 手柄动作键配置组（Xbox 和 DS4 各一套）。"""
        background_group = ExpandSettingCardGroup(
            icon=FluentIcon.ROBOT,
            title='后台模式（测试版）',
            content='需要虚拟手柄驱动和 PrintWindow 截图方式。运行时会短暂抢占鼠标进行点击操作，无需游戏窗口置顶。请勿在前台玩支持手柄的游戏。',
        )

        self.background_mode_switch = SwitchSettingCard(
            icon=FluentIcon.ROBOT, title='后台模式（测试版）',
        )
        self.background_mode_switch.value_changed.connect(self._on_background_mode_changed)
        background_group.addHeaderWidget(self.background_mode_switch.btn)

        self.background_gamepad_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='后台手柄类型',
            options_enum=GamepadTypeEnum,
        )
        self.background_gamepad_type_opt.value_changed.connect(self._toggle_action_cards)
        background_group.addHeaderWidget(self.background_gamepad_type_opt.combo_box)

        self.mouse_flash_duration_opt = DoubleSpinBoxSettingCard(
            icon=FluentIcon.SPEED_HIGH, title='闪切时长（秒）',
            content='后台模式切换键鼠输入时的前台停留时长，过小可能切换失败',
            minimum=0.01, maximum=0.2, step=0.01,
        )
        background_group.addSettingCard(self.mouse_flash_duration_opt)

        # Xbox 动作键卡片
        self._xbox_action_cards: dict[str, GamepadActionKeyCard] = {}
        for action in GamepadActionEnum:
            action_name: str = action.value.value
            if not action_name:
                continue
            card = GamepadActionKeyCard(
                icon=FluentIcon.GAME,
                title=action.value.ui_text,
                modifier_enum=XboxButtonEnum,
                button_enum=XboxButtonEnum,
            )
            self._xbox_action_cards[action_name] = card
            background_group.addSettingCard(card)

        # DS4 动作键卡片
        self._ds4_action_cards: dict[str, GamepadActionKeyCard] = {}
        for action in GamepadActionEnum:
            action_name: str = action.value.value
            if not action_name:
                continue
            card = GamepadActionKeyCard(
                icon=FluentIcon.GAME,
                title=action.value.ui_text,
                modifier_enum=Ds4ButtonEnum,
                button_enum=Ds4ButtonEnum,
            )
            self._ds4_action_cards[action_name] = card
            background_group.addSettingCard(card)

        return background_group

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
                                                      content='仅影响自动战斗。如需使用手柄，请先安装虚拟手柄依赖。',
                                                      options_enum=ControlMethodEnum)
        self.control_method_opt.value_changed.connect(self._on_control_method_changed)
        key_settings_group.addSettingCard(self.control_method_opt)

        self._keyboard_group = self._get_keyboard_group()
        self._gamepad_group = self._get_gamepad_group()
        key_settings_group.addSettingCard(self._keyboard_group)
        key_settings_group.addSettingCard(self._gamepad_group)

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

        gamepad_display_combo = ComboBox()
        gamepad_display_combo.set_items([GamepadTypeEnum.XBOX.value, GamepadTypeEnum.DS4.value])
        gamepad_display_combo.currentIndexChanged.connect(self._toggle_gamepad_cards)
        gamepad_group.addHeaderWidget(gamepad_display_combo)

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

        gamepad_display_combo.setCurrentIndex(0)

        return gamepad_group

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.input_way_opt.init_with_adapter(self.ctx.game_config.type_input_way_adapter)

        self.background_mode_switch.init_with_adapter(self.ctx.game_config.get_prop_adapter('background_mode'))
        self.background_gamepad_type_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('background_gamepad_type'))
        self.mouse_flash_duration_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('mouse_flash_duration'))
        for action_name, card in self._xbox_action_cards.items():
            card.init_with_adapter(self.ctx.game_config.get_prop_adapter(f'xbox_action_{action_name}'))
        for action_name, card in self._ds4_action_cards.items():
            card.init_with_adapter(self.ctx.game_config.get_prop_adapter(f'ds4_action_{action_name}'))
        self._toggle_action_cards()

        self.launch_argument_switch.init_with_adapter(self.ctx.game_config.get_prop_adapter('launch_argument'))
        self.screen_size_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('screen_size'))
        self.full_screen_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('full_screen'))
        self.popup_window_switch.init_with_adapter(self.ctx.game_config.get_prop_adapter('popup_window'))
        self.monitor_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('monitor'))
        self.launch_argument_advance.init_with_adapter(self.ctx.game_config.get_prop_adapter('launch_argument_advance'))

        self.control_method_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('control_method'))

        for action, card in self._key_cards.items():
            card.init_with_adapter(self.ctx.game_config.get_prop_adapter(f'key_{action.value.value}'))

        self.xbox_key_press_time_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_press_time'))
        for action, card in self._xbox_cards.items():
            card.init_with_adapter(self.ctx.game_config.get_prop_adapter(f'xbox_key_{action.value.value}'))

        self.ds4_key_press_time_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_press_time'))
        for action, card in self._ds4_cards.items():
            card.init_with_adapter(self.ctx.game_config.get_prop_adapter(f'ds4_key_{action.value.value}'))

    def _toggle_gamepad_cards(self, index: int) -> None:
        """根据头部下拉框切换 Xbox/DS4 卡片可见性"""
        is_xbox = index == 0

        self.xbox_key_press_time_opt.setVisible(is_xbox)
        for card in self._xbox_cards.values():
            card.setVisible(is_xbox)

        self.ds4_key_press_time_opt.setVisible(not is_xbox)
        for card in self._ds4_cards.values():
            card.setVisible(not is_xbox)

    def _toggle_action_cards(self) -> None:
        """根据配置切换 Xbox/DS4 动作键卡片可见性。"""
        is_xbox = self.ctx.game_config.background_gamepad_type == GamepadTypeEnum.XBOX.value.value
        for card in self._xbox_action_cards.values():
            card.setVisible(is_xbox)
        for card in self._ds4_action_cards.values():
            card.setVisible(not is_xbox)

    def _on_background_mode_changed(self, value: bool) -> None:
        """后台模式开关变更时检查 vgamepad 是否可用。"""
        if value and not pc_button_utils.is_vgamepad_installed():
            self.background_mode_switch.setValue(False, emit_signal=False)
            self.ctx.game_config.background_mode = False
            InfoBar.warning(
                title='后台模式不可用',
                content='未检测到 vgamepad / ViGEmBus，请先安装虚拟手柄驱动',
                parent=self, duration=5000,
            )

    def _on_control_method_changed(self, _index: int, value: str) -> None:
        """操控方式变更时检查 vgamepad 是否可用。"""
        if value != ControlMethodEnum.KEYBOARD.value.value and not pc_button_utils.is_vgamepad_installed():
            self.control_method_opt.setValue(ControlMethodEnum.KEYBOARD.value.value, emit_signal=False)
            self.ctx.game_config.control_method = ControlMethodEnum.KEYBOARD.value.value
            InfoBar.warning(
                title='手柄操控不可用',
                content='未检测到 vgamepad / ViGEmBus，请先安装虚拟手柄驱动',
                parent=self, duration=5000,
            )

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
