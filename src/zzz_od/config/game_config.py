from enum import Enum

from one_dragon.base.config.basic_game_config import BasicGameConfig
from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.controller.pc_button.ds4_button_controller import Ds4ButtonEnum
from one_dragon.base.controller.pc_button.xbox_button_controller import XboxButtonEnum


class GamepadTypeEnum(Enum):

    NONE = ConfigItem('键鼠', 'none')
    XBOX = ConfigItem('Xbox', 'xbox')
    DS4 = ConfigItem('DS4', 'ds4')


class GameKeyAction(Enum):
    """游戏按键动作"""

    INTERACT = ConfigItem('交互', 'interact')
    NORMAL_ATTACK = ConfigItem('普通攻击', 'normal_attack')
    DODGE = ConfigItem('闪避', 'dodge')
    SWITCH_NEXT = ConfigItem('角色切换-下一个', 'switch_next')
    SWITCH_PREV = ConfigItem('角色切换-上一个', 'switch_prev')
    SPECIAL_ATTACK = ConfigItem('特殊攻击', 'special_attack')
    ULTIMATE = ConfigItem('终结技', 'ultimate')
    CHAIN_LEFT = ConfigItem('连携技-左', 'chain_left')
    CHAIN_RIGHT = ConfigItem('连携技-右', 'chain_right')
    MOVE_W = ConfigItem('移动-前', 'move_w')
    MOVE_S = ConfigItem('移动-后', 'move_s')
    MOVE_A = ConfigItem('移动-左', 'move_a')
    MOVE_D = ConfigItem('移动-右', 'move_d')
    LOCK = ConfigItem('锁定敌人', 'lock')
    CHAIN_CANCEL = ConfigItem('连携技-取消', 'chain_cancel')


# 按键默认值：{prefix: {action_value: default}}
_KEY_DEFAULTS: dict[str, dict[str, str]] = {
    'key': {
        'interact': 'f',
        'normal_attack': 'mouse_left',
        'dodge': 'shift',
        'switch_next': 'space',
        'switch_prev': 'c',
        'special_attack': 'e',
        'ultimate': 'q',
        'chain_left': 'q',
        'chain_right': 'e',
        'move_w': 'w',
        'move_s': 's',
        'move_a': 'a',
        'move_d': 'd',
        'lock': 'mouse_middle',
        'chain_cancel': 'mouse_middle',
    },
    'xbox_key': {
        'interact': XboxButtonEnum.A.value.value,
        'normal_attack': XboxButtonEnum.X.value.value,
        'dodge': XboxButtonEnum.A.value.value,
        'switch_next': XboxButtonEnum.RB.value.value,
        'switch_prev': XboxButtonEnum.LB.value.value,
        'special_attack': XboxButtonEnum.Y.value.value,
        'ultimate': XboxButtonEnum.RT.value.value,
        'chain_left': XboxButtonEnum.LB.value.value,
        'chain_right': XboxButtonEnum.RB.value.value,
        'move_w': XboxButtonEnum.L_STICK_W.value.value,
        'move_s': XboxButtonEnum.L_STICK_S.value.value,
        'move_a': XboxButtonEnum.L_STICK_A.value.value,
        'move_d': XboxButtonEnum.L_STICK_D.value.value,
        'lock': XboxButtonEnum.R_THUMB.value.value,
        'chain_cancel': XboxButtonEnum.A.value.value,
    },
    'ds4_key': {
        'interact': Ds4ButtonEnum.CROSS.value.value,
        'normal_attack': Ds4ButtonEnum.SQUARE.value.value,
        'dodge': Ds4ButtonEnum.CROSS.value.value,
        'switch_next': Ds4ButtonEnum.R1.value.value,
        'switch_prev': Ds4ButtonEnum.L1.value.value,
        'special_attack': Ds4ButtonEnum.TRIANGLE.value.value,
        'ultimate': Ds4ButtonEnum.R2.value.value,
        'chain_left': Ds4ButtonEnum.L1.value.value,
        'chain_right': Ds4ButtonEnum.R1.value.value,
        'move_w': Ds4ButtonEnum.L_STICK_W.value.value,
        'move_s': Ds4ButtonEnum.L_STICK_S.value.value,
        'move_a': Ds4ButtonEnum.L_STICK_A.value.value,
        'move_d': Ds4ButtonEnum.L_STICK_D.value.value,
        'lock': Ds4ButtonEnum.R_THUMB.value.value,
        'chain_cancel': Ds4ButtonEnum.CROSS.value.value,
    },
}


def _with_key_properties(cls):
    """根据 GameKeyAction 和 _KEY_DEFAULTS 动态生成按键 property"""

    def _create_getter(name: str, default_value: str):
        def getter(self) -> str:
            return self.get(name, default_value)
        return getter

    def _create_setter(name: str):
        def setter(self, new_value: str) -> None:
            self.update(name, new_value)
        return setter

    for prefix, defaults in _KEY_DEFAULTS.items():
        for action in GameKeyAction:
            prop_name = f'{prefix}_{action.value.value}'
            default = defaults[action.value.value]
            prop = property(_create_getter(prop_name, default), _create_setter(prop_name))
            setattr(cls, prop_name, prop)
    return cls


@_with_key_properties
class GameConfig(BasicGameConfig):

    @property
    def gamepad_type(self) -> str:
        return self.get('gamepad_type', GamepadTypeEnum.NONE.value.value)

    @gamepad_type.setter
    def gamepad_type(self, new_value: str) -> None:
        self.update('gamepad_type', new_value)

    @property
    def xbox_key_press_time(self) -> float:
        return self.get('xbox_key_press_time', 0.02)

    @xbox_key_press_time.setter
    def xbox_key_press_time(self, new_value: float) -> None:
        self.update('xbox_key_press_time', new_value)

    @property
    def ds4_key_press_time(self) -> float:
        return self.get('ds4_key_press_time', 0.02)

    @ds4_key_press_time.setter
    def ds4_key_press_time(self, new_value: float) -> None:
        self.update('ds4_key_press_time', new_value)

    @property
    def original_hdr_value(self) -> str:
        return self.get('original_hdr_value', '')

    @original_hdr_value.setter
    def original_hdr_value(self, new_value: str) -> None:
        self.update('original_hdr_value', new_value)

    @property
    def turn_dx(self) -> float:
        """
        转向时 每度所需要移动的像素距离
        :return:
        """
        return self.get('turn_dx', 0)

    @turn_dx.setter
    def turn_dx(self, new_value: float):
        self.update('turn_dx', new_value)
