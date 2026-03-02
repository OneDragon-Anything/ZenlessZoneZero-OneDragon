from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, PushButton, SettingCardGroup

from one_dragon.base.config.basic_game_config import (
    FullScreenEnum,
    MonitorEnum,
    ScreenSizeEnum,
    TypeInputWay,
)
from one_dragon.base.controller.pc_button.ds4_button_controller import Ds4ButtonEnum
from one_dragon.base.controller.pc_button.xbox_button_controller import XboxButtonEnum
from one_dragon.utils import cmd_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.dual_combo_box_setting_card import (
    DualComboBoxSettingCard,
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
    BackgroundGamepadTypeEnum,
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
        content_widget.add_widget(self._get_launch_argument_group())
        content_widget.add_widget(self._get_key_group())
        content_widget.add_widget(self._get_gamepad_group())
        content_widget.add_widget(self._get_gamepad_action_group())
        content_widget.add_stretch(1)

        return content_widget

    def _get_basic_group(self) -> QWidget:
        basic_group = SettingCardGroup(gt('游戏基础'))

        self.input_way_opt = ComboBoxSettingCard(icon=FluentIcon.CLIPPING_TOOL, title='输入方式',
                                                 options_enum=TypeInputWay)
        basic_group.addSettingCard(self.input_way_opt)

        self.background_mode_switch = SwitchSettingCard(
            icon=FluentIcon.SPEED_OFF, title='后台模式',
            content='启用后使用虚拟手柄操作，无需窗口置顶',
        )
        self.background_mode_switch.value_changed.connect(self._on_background_mode_changed)
        basic_group.addSettingCard(self.background_mode_switch)

        self.hdr_btn_enable = PushButton(text=gt('启用 HDR'), icon=FluentIcon.SETTING, parent=self)
        self.hdr_btn_enable.clicked.connect(self._on_hdr_enable_clicked)
        self.hdr_btn_disable = PushButton(text=gt('禁用 HDR'), icon=FluentIcon.SETTING, parent=self)
        self.hdr_btn_disable.clicked.connect(self._on_hdr_disable_clicked)
        self.hdr_btn = MultiPushSettingCard(icon=FluentIcon.SETTING, title='切换 HDR 状态',
                                            content='仅影响手动启动游戏，一条龙启动游戏会自动禁用 HDR',
                                            btn_list=[self.hdr_btn_disable, self.hdr_btn_enable])
        basic_group.addSettingCard(self.hdr_btn)

        return basic_group

    def _get_launch_argument_group(self) -> QWidget:
        launch_argument_group = SettingCardGroup(gt('启动参数'))

        self.launch_argument_switch = SwitchSettingCard(icon=FluentIcon.SETTING, title='启用')
        self.launch_argument_switch.value_changed.connect(self._on_launch_argument_switch_changed)
        launch_argument_group.addSettingCard(self.launch_argument_switch)

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

    def _get_key_group(self) -> QWidget:
        key_group = SettingCardGroup(gt('游戏按键'))

        self.key_normal_attack_opt = KeySettingCard(icon=FluentIcon.GAME, title='普通攻击')
        key_group.addSettingCard(self.key_normal_attack_opt)

        self.key_dodge_opt = KeySettingCard(icon=FluentIcon.GAME, title='闪避')
        key_group.addSettingCard(self.key_dodge_opt)

        self.key_switch_next_opt = KeySettingCard(icon=FluentIcon.GAME, title='角色切换-下一个')
        key_group.addSettingCard(self.key_switch_next_opt)

        self.key_switch_prev_opt = KeySettingCard(icon=FluentIcon.GAME, title='角色切换-上一个')
        key_group.addSettingCard(self.key_switch_prev_opt)

        self.key_special_attack_opt = KeySettingCard(icon=FluentIcon.GAME, title='特殊攻击')
        key_group.addSettingCard(self.key_special_attack_opt)

        self.key_ultimate_opt = KeySettingCard(icon=FluentIcon.GAME, title='终结技')
        key_group.addSettingCard(self.key_ultimate_opt)

        self.key_interact_opt = KeySettingCard(icon=FluentIcon.GAME, title='交互')
        key_group.addSettingCard(self.key_interact_opt)

        self.key_chain_left_opt = KeySettingCard(icon=FluentIcon.GAME, title='连携技-左')
        key_group.addSettingCard(self.key_chain_left_opt)

        self.key_chain_right_opt = KeySettingCard(icon=FluentIcon.GAME, title='连携技-右')
        key_group.addSettingCard(self.key_chain_right_opt)

        self.key_move_w_opt = KeySettingCard(icon=FluentIcon.GAME, title='移动-前')
        key_group.addSettingCard(self.key_move_w_opt)

        self.key_move_s_opt = KeySettingCard(icon=FluentIcon.GAME, title='移动-后')
        key_group.addSettingCard(self.key_move_s_opt)

        self.key_move_a_opt = KeySettingCard(icon=FluentIcon.GAME, title='移动-左')
        key_group.addSettingCard(self.key_move_a_opt)

        self.key_move_d_opt = KeySettingCard(icon=FluentIcon.GAME, title='移动-右')
        key_group.addSettingCard(self.key_move_d_opt)

        self.key_lock_opt = KeySettingCard(icon=FluentIcon.GAME, title='锁定敌人')
        key_group.addSettingCard(self.key_lock_opt)

        self.key_chain_cancel_opt = KeySettingCard(icon=FluentIcon.GAME, title='连携技-取消')
        key_group.addSettingCard(self.key_chain_cancel_opt)

        return key_group

    def _get_gamepad_group(self) -> QWidget:
        gamepad_group = SettingCardGroup(gt('手柄按键'))

        self.gamepad_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME, title='手柄类型',
            content='需先安装虚拟手柄依赖，参考文档或使用安装器。仅在闪避助手生效。',
            options_enum=GamepadTypeEnum
        )
        self.gamepad_type_opt.value_changed.connect(self._on_gamepad_type_changed)
        gamepad_group.addSettingCard(self.gamepad_type_opt)

        # xbox
        self.xbox_key_press_time_opt = DoubleSpinBoxSettingCard(icon=FluentIcon.GAME, title='单次按键持续时间(秒)',
                                                                content='自行调整，过小可能按键被吞，过大可能影响操作')
        gamepad_group.addSettingCard(self.xbox_key_press_time_opt)

        self.xbox_key_normal_attack_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='普通攻击', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_normal_attack_opt)

        self.xbox_key_dodge_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='闪避', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_dodge_opt)

        self.xbox_key_switch_next_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='角色切换-下一个', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_switch_next_opt)

        self.xbox_key_switch_prev_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='角色切换-上一个', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_switch_prev_opt)

        self.xbox_key_special_attack_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='特殊攻击', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_special_attack_opt)

        self.xbox_key_ultimate_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='终结技', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_ultimate_opt)

        self.xbox_key_interact_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='交互', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_interact_opt)

        self.xbox_key_chain_left_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='连携技-左', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_chain_left_opt)

        self.xbox_key_chain_right_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='连携技-右', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_chain_right_opt)

        self.xbox_key_move_w_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='移动-前', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_move_w_opt)

        self.xbox_key_move_s_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='移动-后', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_move_s_opt)

        self.xbox_key_move_a_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='移动-左', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_move_a_opt)

        self.xbox_key_move_d_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='移动-右', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_move_d_opt)

        self.xbox_key_lock_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='锁定敌人', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_lock_opt)

        self.xbox_key_chain_cancel_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='连携技-取消', options_enum=XboxButtonEnum)
        gamepad_group.addSettingCard(self.xbox_key_chain_cancel_opt)

        # ds4
        self.ds4_key_press_time_opt = DoubleSpinBoxSettingCard(icon=FluentIcon.GAME, title='单次按键持续时间(秒)',
                                                               content='自行调整，过小可能按键被吞，过大可能影响操作')
        gamepad_group.addSettingCard(self.ds4_key_press_time_opt)

        self.ds4_key_normal_attack_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='普通攻击', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_normal_attack_opt)

        self.ds4_key_dodge_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='闪避', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_dodge_opt)

        self.ds4_key_switch_next_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='角色切换-下一个', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_switch_next_opt)

        self.ds4_key_switch_prev_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='角色切换-上一个', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_switch_prev_opt)

        self.ds4_key_special_attack_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='特殊攻击', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_special_attack_opt)

        self.ds4_key_ultimate_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='终结技', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_ultimate_opt)

        self.ds4_key_interact_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='交互', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_interact_opt)

        self.ds4_key_chain_left_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='连携技-左', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_chain_left_opt)

        self.ds4_key_chain_right_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='连携技-右', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_chain_right_opt)

        self.ds4_key_move_w_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='移动-前', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_move_w_opt)

        self.ds4_key_move_s_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='移动-后', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_move_s_opt)

        self.ds4_key_move_a_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='移动-左', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_move_a_opt)

        self.ds4_key_move_d_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='移动-右', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_move_d_opt)

        self.ds4_key_lock_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='锁定敌人', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_lock_opt)

        self.ds4_key_chain_cancel_opt = ComboBoxSettingCard(icon=FluentIcon.GAME, title='连携技-取消', options_enum=Ds4ButtonEnum)
        gamepad_group.addSettingCard(self.ds4_key_chain_cancel_opt)

        return gamepad_group

    def _get_gamepad_action_group(self) -> QWidget:
        """后台模式手柄动作键配置组（Xbox 和 DS4 各一套）。"""
        group = SettingCardGroup('后台模式手柄键')

        self.background_gamepad_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title='后台手柄类型',
            options_enum=BackgroundGamepadTypeEnum,
        )
        self.background_gamepad_type_opt.value_changed.connect(self._on_background_gamepad_type_changed)
        group.addSettingCard(self.background_gamepad_type_opt)

        # Xbox 动作键卡片
        self._xbox_action_cards: dict[str, DualComboBoxSettingCard] = {}
        for action in GamepadActionEnum:
            action_name: str = action.value.value
            if not action_name:
                continue
            card = DualComboBoxSettingCard(
                icon=FluentIcon.GAME,
                title=action.value.ui_text,
                modifier_enum=XboxButtonEnum,
                button_enum=XboxButtonEnum,
            )
            self._xbox_action_cards[action_name] = card
            group.addSettingCard(card)

        # DS4 动作键卡片
        self._ds4_action_cards: dict[str, DualComboBoxSettingCard] = {}
        for action in GamepadActionEnum:
            action_name: str = action.value.value
            if not action_name:
                continue
            card = DualComboBoxSettingCard(
                icon=FluentIcon.GAME,
                title=action.value.ui_text,
                modifier_enum=Ds4ButtonEnum,
                button_enum=Ds4ButtonEnum,
            )
            self._ds4_action_cards[action_name] = card
            group.addSettingCard(card)

        return group

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.input_way_opt.init_with_adapter(self.ctx.game_config.type_input_way_adapter)
        self.background_mode_switch.init_with_adapter(self.ctx.game_config.get_prop_adapter('background_mode'))

        self.launch_argument_switch.init_with_adapter(self.ctx.game_config.get_prop_adapter('launch_argument'))
        self.screen_size_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('screen_size'))
        self.full_screen_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('full_screen'))
        self.popup_window_switch.init_with_adapter(self.ctx.game_config.get_prop_adapter('popup_window'))
        self.monitor_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('monitor'))
        self.launch_argument_advance.init_with_adapter(self.ctx.game_config.get_prop_adapter('launch_argument_advance'))
        self._update_launch_argument_part()

        self.key_normal_attack_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_normal_attack'))
        self.key_dodge_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_dodge'))
        self.key_switch_next_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_switch_next'))
        self.key_switch_prev_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_switch_prev'))
        self.key_special_attack_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_special_attack'))
        self.key_ultimate_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_ultimate'))
        self.key_interact_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_interact'))
        self.key_chain_left_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_chain_left'))
        self.key_chain_right_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_chain_right'))
        self.key_move_w_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_move_w'))
        self.key_move_s_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_move_s'))
        self.key_move_a_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_move_a'))
        self.key_move_d_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_move_d'))
        self.key_lock_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_lock'))
        self.key_chain_cancel_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('key_chain_cancel'))

        self._update_gamepad_part()

        # 后台模式手柄动作键
        self.background_gamepad_type_opt.init_with_adapter(
            self.ctx.game_config.get_prop_adapter('background_gamepad_type'))
        self._update_background_action_visibility()

        for action_name, card in self._xbox_action_cards.items():
            card.init_with_adapter(self.ctx.game_config.get_prop_adapter(f'xbox_action_{action_name}'))
        for action_name, card in self._ds4_action_cards.items():
            card.init_with_adapter(self.ctx.game_config.get_prop_adapter(f'ds4_action_{action_name}'))

    def _update_gamepad_part(self) -> None:
        """手柄部分更新显示。"""
        self.gamepad_type_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('gamepad_type'))

        is_xbox = self.ctx.game_config.gamepad_type == GamepadTypeEnum.XBOX.value.value

        self.xbox_key_press_time_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_press_time'))
        self.xbox_key_normal_attack_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_normal_attack'))
        self.xbox_key_dodge_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_dodge'))
        self.xbox_key_switch_next_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_switch_next'))
        self.xbox_key_switch_prev_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_switch_prev'))
        self.xbox_key_special_attack_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_special_attack'))
        self.xbox_key_ultimate_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_ultimate'))
        self.xbox_key_interact_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_interact'))
        self.xbox_key_chain_left_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_chain_left'))
        self.xbox_key_chain_right_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_chain_right'))
        self.xbox_key_move_w_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_move_w'))
        self.xbox_key_move_s_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_move_s'))
        self.xbox_key_move_a_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_move_a'))
        self.xbox_key_move_d_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_move_d'))
        self.xbox_key_lock_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_lock'))
        self.xbox_key_chain_cancel_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_chain_cancel'))

        self.xbox_key_press_time_opt.setVisible(is_xbox)
        self.xbox_key_normal_attack_opt.setVisible(is_xbox)
        self.xbox_key_dodge_opt.setVisible(is_xbox)
        self.xbox_key_switch_next_opt.setVisible(is_xbox)
        self.xbox_key_switch_prev_opt.setVisible(is_xbox)
        self.xbox_key_special_attack_opt.setVisible(is_xbox)
        self.xbox_key_ultimate_opt.setVisible(is_xbox)
        self.xbox_key_interact_opt.setVisible(is_xbox)
        self.xbox_key_chain_left_opt.setVisible(is_xbox)
        self.xbox_key_chain_right_opt.setVisible(is_xbox)
        self.xbox_key_move_w_opt.setVisible(is_xbox)
        self.xbox_key_move_s_opt.setVisible(is_xbox)
        self.xbox_key_move_a_opt.setVisible(is_xbox)
        self.xbox_key_move_d_opt.setVisible(is_xbox)
        self.xbox_key_lock_opt.setVisible(is_xbox)
        self.xbox_key_chain_cancel_opt.setVisible(is_xbox)

        is_ds4 = self.ctx.game_config.gamepad_type == GamepadTypeEnum.DS4.value.value

        self.ds4_key_press_time_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_press_time'))
        self.ds4_key_normal_attack_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_normal_attack'))
        self.ds4_key_dodge_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_dodge'))
        self.ds4_key_switch_next_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_switch_next'))
        self.ds4_key_switch_prev_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_switch_prev'))
        self.ds4_key_special_attack_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_special_attack'))
        self.ds4_key_ultimate_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_ultimate'))
        self.ds4_key_interact_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_interact'))
        self.ds4_key_chain_left_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_chain_left'))
        self.ds4_key_chain_right_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_chain_right'))
        self.ds4_key_move_w_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_move_w'))
        self.ds4_key_move_s_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_move_s'))
        self.ds4_key_move_a_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_move_a'))
        self.ds4_key_move_d_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_move_d'))
        self.ds4_key_lock_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_lock'))
        self.ds4_key_chain_cancel_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_chain_cancel'))

        self.ds4_key_press_time_opt.setVisible(is_ds4)
        self.ds4_key_normal_attack_opt.setVisible(is_ds4)
        self.ds4_key_dodge_opt.setVisible(is_ds4)
        self.ds4_key_switch_next_opt.setVisible(is_ds4)
        self.ds4_key_switch_prev_opt.setVisible(is_ds4)
        self.ds4_key_special_attack_opt.setVisible(is_ds4)
        self.ds4_key_ultimate_opt.setVisible(is_ds4)
        self.ds4_key_interact_opt.setVisible(is_ds4)
        self.ds4_key_chain_left_opt.setVisible(is_ds4)
        self.ds4_key_chain_right_opt.setVisible(is_ds4)
        self.ds4_key_move_w_opt.setVisible(is_ds4)
        self.ds4_key_move_s_opt.setVisible(is_ds4)
        self.ds4_key_move_a_opt.setVisible(is_ds4)
        self.ds4_key_move_d_opt.setVisible(is_ds4)
        self.ds4_key_lock_opt.setVisible(is_ds4)
        self.ds4_key_chain_cancel_opt.setVisible(is_ds4)

    def _on_gamepad_type_changed(self, idx: int, value: str) -> None:
        self._update_gamepad_part()

    def _update_background_action_visibility(self) -> None:
        """根据后台手柄类型显示/隐藏对应动作键卡片。"""
        bg_type = self.ctx.game_config.background_gamepad_type
        is_xbox = bg_type == BackgroundGamepadTypeEnum.XBOX.value.value
        is_ds4 = bg_type == BackgroundGamepadTypeEnum.DS4.value.value
        for card in self._xbox_action_cards.values():
            card.setVisible(is_xbox)
        for card in self._ds4_action_cards.values():
            card.setVisible(is_ds4)

    def _on_background_gamepad_type_changed(self, idx: int, value: str) -> None:
        self._update_background_action_visibility()
        if self.ctx.game_config.background_mode:
            self.ctx.controller.enable_background_mode(value)

    def _on_background_mode_changed(self) -> None:
        """后台模式开关切换时同步控制器状态。"""
        if self.ctx.game_config.background_mode:
            self.ctx.controller.enable_background_mode(self.ctx.game_config.background_gamepad_type)
        else:
            self.ctx.controller.enable_foreground_mode()

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

    def _update_launch_argument_part(self) -> None:
        """启动参数部分更新显示。"""
        value = self.ctx.game_config.launch_argument
        self.screen_size_opt.setVisible(value)
        self.full_screen_opt.setVisible(value)
        self.popup_window_switch.setVisible(value)
        self.monitor_opt.setVisible(value)
        self.launch_argument_advance.setVisible(value)

    def _on_launch_argument_switch_changed(self) -> None:
        self._update_launch_argument_part()
