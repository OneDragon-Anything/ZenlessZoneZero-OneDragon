from enum import Enum

from one_dragon.base.config.basic_game_config import BasicGameConfig
from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.controller.pc_button.ds4_button_controller import Ds4ButtonEnum
from one_dragon.base.controller.pc_button.xbox_button_controller import XboxButtonEnum


class ControlMethodEnum(Enum):

    KEYBOARD = ConfigItem('键鼠', 'keyboard')
    XBOX = ConfigItem('Xbox', 'xbox')
    DS4 = ConfigItem('DS4', 'ds4')


class GamepadTypeEnum(Enum):

    XBOX = ConfigItem('Xbox', 'xbox')
    DS4 = ConfigItem('DS4', 'ds4')


class GamepadActionEnum(Enum):
    """后台模式下用手柄按键替代点击的逻辑动作。

    value 是 ConfigItem(显示名, 存储值)。
    screen 区域的 gamepad_key 引用存储值。
    """

    MENU = ConfigItem('菜单', 'menu')
    MAP = ConfigItem('地图', 'map')
    MINIMAP = ConfigItem('小地图', 'minimap')
    COMPENDIUM = ConfigItem('快捷手册', 'compendium')
    GUIDE = ConfigItem('功能导览', 'function_menu')


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

# 后台模式手柄动作键默认值：{prefix: {action_value: default}}
_ACTION_KEY_DEFAULTS: dict[str, dict[str, list[str]]] = {
    'xbox_action': {
        'menu': [XboxButtonEnum.START.value.value],
        'map': [XboxButtonEnum.DPAD_RIGHT.value.value],
        'minimap': [XboxButtonEnum.BACK.value.value],
        'compendium': [XboxButtonEnum.LT.value.value, XboxButtonEnum.A.value.value],
        'function_menu': [XboxButtonEnum.LT.value.value, XboxButtonEnum.START.value.value],
    },
    'ds4_action': {
        'menu': [Ds4ButtonEnum.OPTIONS.value.value],
        'map': [Ds4ButtonEnum.DPAD_RIGHT.value.value],
        'minimap': [Ds4ButtonEnum.TOUCHPAD.value.value],
        'compendium': [Ds4ButtonEnum.L2.value.value, Ds4ButtonEnum.CROSS.value.value],
        'function_menu': [Ds4ButtonEnum.L2.value.value, Ds4ButtonEnum.OPTIONS.value.value],
    },
}


def _with_key_properties(cls):
    """根据 _KEY_DEFAULTS 和 _ACTION_KEY_DEFAULTS 动态生成按键 property"""

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

    for prefix, defaults in _ACTION_KEY_DEFAULTS.items():
        for action in GamepadActionEnum:
            prop_name = f'{prefix}_{action.value.value}'
            default = defaults[action.value.value]
            prop = property(_create_getter(prop_name, default), _create_setter(prop_name))
            setattr(cls, prop_name, prop)

    return cls


@_with_key_properties
class GameConfig(BasicGameConfig):

    # 旧数字索引 → 新描述性键名映射（兼容旧版配置）
    _LEGACY_GAMEPAD_KEYS: dict[str, str] = {
        **{f'xbox_{i}': k for i, k in enumerate([
            'xbox_a', 'xbox_b', 'xbox_x', 'xbox_y',
            'xbox_lt', 'xbox_rt', 'xbox_lb', 'xbox_rb',
            'xbox_ls_up', 'xbox_ls_down', 'xbox_ls_left', 'xbox_ls_right',
            'xbox_l_thumb', 'xbox_r_thumb',
        ])},
        **{f'ds4_{i}': k for i, k in enumerate([
            'ds4_cross', 'ds4_circle', 'ds4_square', 'ds4_triangle',
            'ds4_l2', 'ds4_r2', 'ds4_l1', 'ds4_r1',
            'ds4_ls_up', 'ds4_ls_down', 'ds4_ls_left', 'ds4_ls_right',
            'ds4_l_thumb', 'ds4_r_thumb',
        ])},
    }

    def __init__(self, instance_idx: int):
        BasicGameConfig.__init__(self, instance_idx)
        # TODO 迁移旧配置 2026-9 删除
        self._migrate_legacy_keys()
        self._migrate_legacy_gamepad_keys()

    def _migrate_legacy_keys(self) -> None:
        """迁移旧键名到新键名。"""
        _RENAMES = {'gamepad_type': 'control_method'}
        for old_key, new_key in _RENAMES.items():
            old_val = self.get(old_key)
            if old_val is not None and self.get(new_key) is None:
                self.update(new_key, old_val)
                self.update(old_key, None)

    def _migrate_legacy_gamepad_keys(self) -> None:
        """初始化时一次性迁移所有旧数字格式的手柄按键配置。"""
        for prefix in ('xbox_key', 'ds4_key'):
            for action in GameKeyAction:
                prop = f'{prefix}_{action.value.value}'
                value = self.get(prop, '')
                if not value:
                    continue
                migrated = '+'.join(
                    self._LEGACY_GAMEPAD_KEYS.get(p, p) for p in value.split('+')
                )
                if migrated != value:
                    self.update(prop, migrated)

    @property
    def control_method(self) -> str:
        return self.get('control_method', ControlMethodEnum.KEYBOARD.value.value)

    @control_method.setter
    def control_method(self, new_value: str) -> None:
        self.update('control_method', new_value)

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
    def background_mode(self) -> bool:
        return self.get('background_mode', False)

    @background_mode.setter
    def background_mode(self, new_value: bool) -> None:
        self.update('background_mode', new_value)

    @property
    def background_gamepad_type(self) -> str:
        return self.get('background_gamepad_type', GamepadTypeEnum.XBOX.value.value)

    @background_gamepad_type.setter
    def background_gamepad_type(self, new_value: str) -> None:
        self.update('background_gamepad_type', new_value)

    @property
    def mouse_flash_duration(self) -> float:
        """后台模式闪切键鼠模式时每步等待时长（秒）"""
        return self.get('mouse_flash_duration', 0.05)

    @mouse_flash_duration.setter
    def mouse_flash_duration(self, new_value: float) -> None:
        self.update('mouse_flash_duration', new_value)

    def get_action_keys(self, control_method: str) -> dict[str, str]:
        """获取指定控制方式的所有按键映射。

        Args:
            control_method: ControlMethodEnum 的值，如 'keyboard' / 'xbox' / 'ds4'。

        Returns:
            {action_name: key_value}，如 {'dodge': 'shift', 'interact': 'f', ...}
        """
        prefix = 'key' if control_method == 'keyboard' else f'{control_method}_key'
        return {
            action.value.value: getattr(self, f'{prefix}_{action.value.value}')
            for action in GameKeyAction
        }

    def get_gamepad_action_keys(self, gamepad_type: str | None = None) -> dict[str, list[str]]:
        """获取指定手柄类型的后台模式动作 → 实际按键映射。

        Args:
            gamepad_type: GamepadTypeEnum 的值，如 'xbox' / 'ds4'。
                          为 None 时使用当前配置的 background_gamepad_type。

        Returns:
            {action_name: [key, ...]}
        """
        if gamepad_type is None:
            gamepad_type = self.background_gamepad_type
        result: dict[str, list[str]] = {}
        for action in GamepadActionEnum:
            action_name: str = action.value.value
            if not action_name:
                continue
            prop_name = f'{gamepad_type}_action_{action_name}'
            value = getattr(self, prop_name, [])
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
