from enum import Enum

from one_dragon.base.config.basic_game_config import BasicGameConfig
from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.controller.pc_button.ds4_button_controller import Ds4ButtonEnum
from one_dragon.base.controller.pc_button.xbox_button_controller import XboxButtonEnum


class GamepadActionEnum(Enum):
    """后台模式下替代 pc_alt 点击的逻辑动作。

    value 是 ConfigItem(显示名, 存储值)。
    screen 区域的 gamepad_key 引用存储值。
    """

    MENU = ConfigItem('菜单', 'menu')
    MAP = ConfigItem('地图', 'map')
    MINIMAP = ConfigItem('小地图', 'minimap')
    COMPENDIUM = ConfigItem('快捷手册', 'compendium')
    GUIDE = ConfigItem('功能导览', 'function_menu')


class GamepadTypeEnum(Enum):

    NONE = ConfigItem('键鼠', 'none')
    XBOX = ConfigItem('Xbox', 'xbox')
    DS4 = ConfigItem('DS4', 'ds4')


class BackgroundGamepadTypeEnum(Enum):
    """后台模式手柄类型（必须使用虚拟手柄，无 NONE 选项）。"""

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

    # ── 后台模式 ───────────────────────────────

    @property
    def background_mode(self) -> bool:
        return self.get('background_mode', False)

    @background_mode.setter
    def background_mode(self, new_value: bool) -> None:
        self.update('background_mode', new_value)

    @property
    def background_gamepad_type(self) -> str:
        return self.get('background_gamepad_type', BackgroundGamepadTypeEnum.XBOX.value.value)

    @background_gamepad_type.setter
    def background_gamepad_type(self, new_value: str) -> None:
        self.update('background_gamepad_type', new_value)

    # ── 后台模式手柄动作键 ───────────────────────────────

    @property
    def xbox_action_menu(self) -> str:
        return self.get('xbox_action_menu', 'xbox_start')

    @xbox_action_menu.setter
    def xbox_action_menu(self, new_value: str) -> None:
        self.update('xbox_action_menu', new_value)

    @property
    def xbox_action_map(self) -> str:
        return self.get('xbox_action_map', 'xbox_dpad_right')

    @xbox_action_map.setter
    def xbox_action_map(self, new_value: str) -> None:
        self.update('xbox_action_map', new_value)

    @property
    def xbox_action_minimap(self) -> str:
        return self.get('xbox_action_minimap', 'xbox_back')

    @xbox_action_minimap.setter
    def xbox_action_minimap(self, new_value: str) -> None:
        self.update('xbox_action_minimap', new_value)

    @property
    def xbox_action_compendium(self) -> str:
        return self.get('xbox_action_compendium', 'xbox_lb+xbox_a')

    @xbox_action_compendium.setter
    def xbox_action_compendium(self, new_value: str) -> None:
        self.update('xbox_action_compendium', new_value)

    @property
    def xbox_action_function_menu(self) -> str:
        return self.get('xbox_action_function_menu', 'xbox_lb+xbox_start')

    @xbox_action_function_menu.setter
    def xbox_action_function_menu(self, new_value: str) -> None:
        self.update('xbox_action_function_menu', new_value)

    # ── DS4 动作键 ──

    @property
    def ds4_action_menu(self) -> str:
        return self.get('ds4_action_menu', 'ds4_options')

    @ds4_action_menu.setter
    def ds4_action_menu(self, new_value: str) -> None:
        self.update('ds4_action_menu', new_value)

    @property
    def ds4_action_map(self) -> str:
        return self.get('ds4_action_map', 'ds4_dpad_right')

    @ds4_action_map.setter
    def ds4_action_map(self, new_value: str) -> None:
        self.update('ds4_action_map', new_value)

    @property
    def ds4_action_minimap(self) -> str:
        return self.get('ds4_action_minimap', 'ds4_touchpad')

    @ds4_action_minimap.setter
    def ds4_action_minimap(self, new_value: str) -> None:
        self.update('ds4_action_minimap', new_value)

    @property
    def ds4_action_compendium(self) -> str:
        return self.get('ds4_action_compendium', 'ds4_l1+ds4_cross')

    @ds4_action_compendium.setter
    def ds4_action_compendium(self, new_value: str) -> None:
        self.update('ds4_action_compendium', new_value)

    @property
    def ds4_action_function_menu(self) -> str:
        return self.get('ds4_action_function_menu', 'ds4_l1+ds4_options')

    @ds4_action_function_menu.setter
    def ds4_action_function_menu(self, new_value: str) -> None:
        self.update('ds4_action_function_menu', new_value)

    # ── 通用查询 ──

    def get_gamepad_action_keys(self, gamepad_type: str) -> dict[str, str]:
        """获取指定手柄类型的后台模式动作 → 实际按键映射。

        Args:
            gamepad_type: 'xbox' 或 'ds4'

        Returns:
            {action_name: key_combo_str}
        """
        prefix = gamepad_type
        result: dict[str, str] = {}
        for action in GamepadActionEnum:
            action_name: str = action.value.value
            if not action_name:
                continue
            prop_name = f'{prefix}_action_{action_name}'
            value = getattr(self, prop_name, '')
            if value:
                result[action_name] = value
        return result

    @property
    def original_hdr_value(self) -> str:
        return self.get('original_hdr_value', '')

    @original_hdr_value.setter
    def original_hdr_value(self, new_value: str) -> None:
        self.update('original_hdr_value', new_value)

    @property
    def turn_dx(self) -> float:
        """转向时 每度所需要移动的像素距离。"""
        return self.get('turn_dx', 0)

    @turn_dx.setter
    def turn_dx(self, new_value: float):
        self.update('turn_dx', new_value)

    @property
    def gamepad_turn_speed(self) -> float:
        """后台手柄模式下，右摇杆满偏转对应的 每秒等效鼠标像素距离。"""
        return self.get('gamepad_turn_speed', 1000)

    @gamepad_turn_speed.setter
    def gamepad_turn_speed(self, new_value: float):
        self.update('gamepad_turn_speed', new_value)
