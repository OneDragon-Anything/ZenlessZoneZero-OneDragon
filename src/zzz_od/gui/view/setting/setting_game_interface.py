from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, SettingCardGroup, Dialog, PushButton

from one_dragon.base.config.basic_game_config import TypeInputWay, ScreenSizeEnum, FullScreenEnum, MonitorEnum
from one_dragon.base.controller.pc_button.ds4_button_controller import Ds4ButtonEnum
from one_dragon.base.controller.pc_button.xbox_button_controller import XboxButtonEnum
from one_dragon.utils import cmd_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.horizontal_setting_card_group import HorizontalSettingCardGroup
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.help_card import HelpCard
from one_dragon_qt.widgets.setting_card.key_setting_card import KeySettingCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from zzz_od.config.game_config import GamepadTypeEnum
from zzz_od.config.agent_outfit_config import AgentOutfitNicole, AgentOutfitEllen, AgentOutfitAstraYao, AgentOutfitYiXuan
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

        content_widget.add_widget(self._get_agent_outfit_group())
        content_widget.add_widget(self._get_basic_group())
        content_widget.add_widget(self._get_launch_argument_group())
        content_widget.add_widget(self._get_key_group())
        content_widget.add_widget(self._get_gamepad_group())
        content_widget.add_stretch(1)

        return content_widget

    def _get_agent_outfit_group(self) -> QWidget:
        agent_outfit_group = SettingCardGroup(gt('代理人皮肤'))

        self.compatibility_mode_switch = SwitchSettingCard(icon=FluentIcon.INFO, title='兼容模式', content='自动战斗识别出问题的时候可尝试开启')
        self.compatibility_mode_switch.value_changed.connect(self._on_compatibility_mode_changed)
        agent_outfit_group.addSettingCard(self.compatibility_mode_switch)

        self.outfit_nicole_opt = ComboBoxSettingCard(icon=FluentIcon.PEOPLE, title='妮可', options_enum=AgentOutfitNicole)
        self.outfit_nicole_opt.value_changed.connect(self._on_agent_outfit_changed)

        self.outfit_ellen_opt = ComboBoxSettingCard(icon=FluentIcon.PEOPLE, title='艾莲', options_enum=AgentOutfitEllen)
        self.outfit_ellen_opt.value_changed.connect(self._on_agent_outfit_changed)

        self.outfit_astra_yao_opt = ComboBoxSettingCard(icon=FluentIcon.PEOPLE, title='耀嘉音', options_enum=AgentOutfitAstraYao)
        self.outfit_astra_yao_opt.value_changed.connect(self._on_agent_outfit_changed)

        self.outfit_yixuan_opt = ComboBoxSettingCard(icon=FluentIcon.PEOPLE, title='仪玄', options_enum=AgentOutfitYiXuan)
        self.outfit_yixuan_opt.value_changed.connect(self._on_agent_outfit_changed)

        self.agent_outfit_group_horizontal = HorizontalSettingCardGroup([
            self.outfit_nicole_opt,
            self.outfit_ellen_opt,
            self.outfit_astra_yao_opt,
            self.outfit_yixuan_opt
        ])
        agent_outfit_group.addSettingCard(self.agent_outfit_group_horizontal)

        return agent_outfit_group

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
        self.xbox_key_press_time_opt = TextSettingCard(icon=FluentIcon.GAME, title='单次按键持续时间(秒)',
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
        self.ds4_key_press_time_opt = TextSettingCard(icon=FluentIcon.GAME, title='单次按键持续时间(秒)',
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

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.compatibility_mode_switch.init_with_adapter(self.ctx.agent_outfit_config.get_prop_adapter('compatibility_mode'))
        self.outfit_nicole_opt.init_with_adapter(self.ctx.agent_outfit_config.get_prop_adapter('nicole'))
        self.outfit_ellen_opt.init_with_adapter(self.ctx.agent_outfit_config.get_prop_adapter('ellen'))
        self.outfit_astra_yao_opt.init_with_adapter(self.ctx.agent_outfit_config.get_prop_adapter('astra_yao'))
        self.outfit_yixuan_opt.init_with_adapter(self.ctx.agent_outfit_config.get_prop_adapter('yixuan'))
        self._update_agent_outfit_options(self.ctx.agent_outfit_config.compatibility_mode)

        self.input_way_opt.init_with_adapter(self.ctx.game_config.type_input_way_adapter)

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

    def _update_gamepad_part(self) -> None:
        """
        手柄部分更新显示
        :return:
        """
        self.gamepad_type_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('gamepad_type'))

        is_xbox = self.ctx.game_config.gamepad_type == GamepadTypeEnum.XBOX.value.value

        self.xbox_key_press_time_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('xbox_key_press_time', 'str', 'float'))
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

        self.ds4_key_press_time_opt.init_with_adapter(self.ctx.game_config.get_prop_adapter('ds4_key_press_time', 'str', 'float'))
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

    def _on_compatibility_mode_changed(self, value: bool) -> None:
        self.ctx.agent_outfit_config.compatibility_mode = value
        if value:
            self.ctx.init_agent_template_id()
        else:
            self.ctx.init_agent_template_id_list()
        self._update_agent_outfit_options(value)

    def _update_agent_outfit_options(self, value: bool) -> None:
        self.agent_outfit_group_horizontal.setVisible(value)

    def _on_agent_outfit_changed(self) -> None:
        if self.ctx.agent_outfit_config.compatibility_mode:
            self.ctx.init_agent_template_id()

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
        """
        启动参数部分更新显示
        :return:
        """
        value = self.ctx.game_config.launch_argument
        self.screen_size_opt.setVisible(value)
        self.full_screen_opt.setVisible(value)
        self.popup_window_switch.setVisible(value)
        self.monitor_opt.setVisible(value)
        self.launch_argument_advance.setVisible(value)

    def _on_launch_argument_switch_changed(self) -> None:
        self._update_launch_argument_part()
