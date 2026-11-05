from enum import Enum

from one_dragon.base.config.basic_game_config import BasicGameConfig
from one_dragon.base.config.config_item import ConfigItem


class GameKeyAction(Enum):
    """游戏按键动作"""

    INTERACT = ConfigItem('交互', 'interact')
    NORMAL_ATTACK = ConfigItem('普通攻击', 'normal_attack')
    DODGE = ConfigItem('闪避', 'dodge')
    SWITCH_NEXT = ConfigItem('角色切换-下一个', 'switch_next')
    SWITCH_PREV = ConfigItem('角色切换-上一个', 'switch_prev')
    SWITCH_BACKUP = ConfigItem('切换后援', 'switch_backup')
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
_KEY_DEFAULTS: dict[str, str] = {
    'interact': 'f',
    'normal_attack': 'mouse_left',
    'dodge': 'shift',
    'switch_next': 'space',
    'switch_prev': 'c',
    'switch_backup': 'r',
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
}

def _with_key_properties(cls):
    """根据键盘按键默认值动态生成属性。"""

    def _create_getter(name: str, default_value: str):
        def getter(self) -> str:
            return self.get(name, default_value)
        return getter

    def _create_setter(name: str):
        def setter(self, new_value: str) -> None:
            self.update(name, new_value)
        return setter

    for action in GameKeyAction:
        prop_name = f'key_{action.value.value}'
        default = _KEY_DEFAULTS[action.value.value]
        prop = property(_create_getter(prop_name, default), _create_setter(prop_name))
        setattr(cls, prop_name, prop)

    return cls


@_with_key_properties
class GameConfig(BasicGameConfig):

    def __init__(self, instance_idx: int):
        BasicGameConfig.__init__(self, instance_idx)
    def get_action_keys(self) -> dict[str, str]:
        """获取游戏动作对应的键盘按键。"""
        return {
            action.value.value: getattr(self, f'key_{action.value.value}')
            for action in GameKeyAction
        }

    @property
    def original_hdr_value(self) -> str:
        return self.get('original_hdr_value', '')

    @original_hdr_value.setter
    def original_hdr_value(self, new_value: str) -> None:
        self.update('original_hdr_value', new_value)

    @property
    def turn_dx(self) -> float:
        """转向时 每度所需要移动的像素距离。"""
        return self.get('turn_dx', -5.5)  # 游戏内镜头灵敏度（X轴）为默认值3时的经验兜底值

    @turn_dx.setter
    def turn_dx(self, new_value: float):
        self.update('turn_dx', new_value)
