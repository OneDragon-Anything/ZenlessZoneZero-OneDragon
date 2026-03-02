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

    NONE = ConfigItem('无', '')
    INTERACT = ConfigItem('交互', 'interact')
    MENU = ConfigItem('菜单', 'menu')
    MAP = ConfigItem('地图', 'map')
    MINIMAP = ConfigItem('小地图', 'minimap')
    COMPENDIUM = ConfigItem('快捷手册', 'compendium')
    GUIDE = ConfigItem('功能导览', 'function_menu')


class GamepadTypeEnum(Enum):

    NONE = ConfigItem('无', 'none')
    XBOX = ConfigItem('Xbox', 'xbox')
    DS4 = ConfigItem('DS4', 'ds4')


class BackgroundGamepadTypeEnum(Enum):
    """后台模式手柄类型（必须使用虚拟手柄，无 NONE 选项）。"""

    XBOX = ConfigItem('Xbox', 'xbox')
    DS4 = ConfigItem('DS4', 'ds4')


class GameConfig(BasicGameConfig):

    def __init__(self, instance_idx: int):
        BasicGameConfig.__init__(self, instance_idx)
        self._migrate_legacy_gamepad_keys()

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

    def _migrate_gamepad_key(self, value: str) -> str:
        """迁移旧数字格式手柄键到新描述性格式。

        支持单键 ('xbox_0' → 'xbox_a') 和组合键 ('xbox_6+xbox_0' → 'xbox_lb+xbox_a')。
        """
        parts = value.split('+')
        migrated = [self._LEGACY_GAMEPAD_KEYS.get(p, p) for p in parts]
        return '+'.join(migrated)

    def _migrate_legacy_gamepad_keys(self) -> None:
        """初始化时一次性迁移所有旧数字格式的手柄按键配置。"""
        key_props = [
            # Xbox 战斗按键
            'xbox_key_normal_attack', 'xbox_key_dodge',
            'xbox_key_switch_next', 'xbox_key_switch_prev',
            'xbox_key_special_attack', 'xbox_key_ultimate',
            'xbox_key_interact', 'xbox_key_chain_left', 'xbox_key_chain_right',
            'xbox_key_move_w', 'xbox_key_move_s', 'xbox_key_move_a', 'xbox_key_move_d',
            'xbox_key_lock', 'xbox_key_chain_cancel',
            # DS4 战斗按键
            'ds4_key_normal_attack', 'ds4_key_dodge',
            'ds4_key_switch_next', 'ds4_key_switch_prev',
            'ds4_key_special_attack', 'ds4_key_ultimate',
            'ds4_key_interact', 'ds4_key_chain_left', 'ds4_key_chain_right',
            'ds4_key_move_w', 'ds4_key_move_s', 'ds4_key_move_a', 'ds4_key_move_d',
            'ds4_key_lock', 'ds4_key_chain_cancel',
        ]
        for prop in key_props:
            value = self.get(prop, '')
            if not value:
                continue
            migrated = self._migrate_gamepad_key(value)
            if migrated != value:
                self.update(prop, migrated)

    @property
    def key_normal_attack(self) -> str:
        return self.get('key_normal_attack', 'mouse_left')

    @key_normal_attack.setter
    def key_normal_attack(self, new_value: str) -> None:
        self.update('key_normal_attack', new_value)

    @property
    def background_mode(self) -> bool:
        return self.get('background_mode', False)

    @background_mode.setter
    def background_mode(self, new_value: bool) -> None:
        self.update('background_mode', new_value)

    @property
    def key_dodge(self) -> str:
        return self.get('key_dodge', 'shift')

    @key_dodge.setter
    def key_dodge(self, new_value: str) -> None:
        self.update('key_dodge', new_value)

    @property
    def key_switch_next(self) -> str:
        return self.get('key_switch_next', 'space')

    @key_switch_next.setter
    def key_switch_next(self, new_value: str) -> None:
        self.update('key_switch_next', new_value)

    @property
    def key_switch_prev(self) -> str:
        return self.get('key_switch_prev', 'c')

    @key_switch_prev.setter
    def key_switch_prev(self, new_value: str) -> None:
        self.update('key_switch_prev', new_value)

    @property
    def key_special_attack(self) -> str:
        return self.get('key_special_attack', 'e')

    @key_special_attack.setter
    def key_special_attack(self, new_value: str) -> None:
        self.update('key_special_attack', new_value)

    @property
    def key_ultimate(self) -> str:
        """爆发技"""
        return self.get('key_ultimate', 'q')

    @key_ultimate.setter
    def key_ultimate(self, new_value: str) -> None:
        self.update('key_ultimate', new_value)

    @property
    def key_interact(self) -> str:
        """交互"""
        return self.get('key_interact', 'f')

    @key_interact.setter
    def key_interact(self, new_value: str) -> None:
        self.update('key_interact', new_value)

    @property
    def key_chain_left(self) -> str:
        return self.get('key_chain_left', 'q')

    @key_chain_left.setter
    def key_chain_left(self, new_value: str) -> None:
        self.update('key_chain_left', new_value)

    @property
    def key_chain_right(self) -> str:
        return self.get('key_chain_right', 'e')

    @key_chain_right.setter
    def key_chain_right(self, new_value: str) -> None:
        self.update('key_chain_right', new_value)

    @property
    def key_move_w(self) -> str:
        return self.get('key_move_w', 'w')

    @key_move_w.setter
    def key_move_w(self, new_value: str) -> None:
        self.update('key_move_w', new_value)

    @property
    def key_move_s(self) -> str:
        return self.get('key_move_s', 's')

    @key_move_s.setter
    def key_move_s(self, new_value: str) -> None:
        self.update('key_move_s', new_value)

    @property
    def key_move_a(self) -> str:
        return self.get('key_move_a', 'a')

    @key_move_a.setter
    def key_move_a(self, new_value: str) -> None:
        self.update('key_move_a', new_value)

    @property
    def key_move_d(self) -> str:
        return self.get('key_move_d', 'd')

    @key_move_d.setter
    def key_move_d(self, new_value: str) -> None:
        self.update('key_move_d', new_value)

    @property
    def key_lock(self) -> str:
        return self.get('key_lock', 'mouse_middle')

    @key_lock.setter
    def key_lock(self, new_value: str) -> None:
        self.update('key_lock', new_value)

    @property
    def key_chain_cancel(self) -> str:
        return self.get('key_chain_cancel', 'mouse_middle')

    @key_chain_cancel.setter
    def key_chain_cancel(self, new_value: str) -> None:
        self.update('key_chain_cancel', new_value)

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
    def xbox_key_normal_attack(self) -> str:
        return self.get('xbox_key_normal_attack', XboxButtonEnum.X.value.value)

    @xbox_key_normal_attack.setter
    def xbox_key_normal_attack(self, new_value: str) -> None:
        self.update('xbox_key_normal_attack', new_value)

    @property
    def xbox_key_dodge(self) -> str:
        return self.get('xbox_key_dodge', XboxButtonEnum.A.value.value)

    @xbox_key_dodge.setter
    def xbox_key_dodge(self, new_value: str) -> None:
        self.update('xbox_key_dodge', new_value)

    @property
    def xbox_key_switch_next(self) -> str:
        return self.get('xbox_key_switch_next', XboxButtonEnum.RB.value.value)

    @xbox_key_switch_next.setter
    def xbox_key_switch_next(self, new_value: str) -> None:
        self.update('xbox_key_switch_next', new_value)

    @property
    def xbox_key_switch_prev(self) -> str:
        return self.get('xbox_key_switch_prev', XboxButtonEnum.LB.value.value)

    @xbox_key_switch_prev.setter
    def xbox_key_switch_prev(self, new_value: str) -> None:
        self.update('xbox_key_switch_prev', new_value)

    @property
    def xbox_key_special_attack(self) -> str:
        return self.get('xbox_key_special_attack', XboxButtonEnum.Y.value.value)

    @xbox_key_special_attack.setter
    def xbox_key_special_attack(self, new_value: str) -> None:
        self.update('xbox_key_special_attack', new_value)

    @property
    def xbox_key_ultimate(self) -> str:
        """爆发技"""
        return self.get('xbox_key_ultimate', XboxButtonEnum.RT.value.value)

    @xbox_key_ultimate.setter
    def xbox_key_ultimate(self, new_value: str) -> None:
        self.update('xbox_key_ultimate', new_value)

    @property
    def xbox_key_interact(self) -> str:
        """交互"""
        return self.get('xbox_key_interact', XboxButtonEnum.A.value.value)

    @xbox_key_interact.setter
    def xbox_key_interact(self, new_value: str) -> None:
        self.update('xbox_key_interact', new_value)

    @property
    def xbox_key_chain_left(self) -> str:
        return self.get('xbox_key_chain_left', XboxButtonEnum.LB.value.value)

    @xbox_key_chain_left.setter
    def xbox_key_chain_left(self, new_value: str) -> None:
        self.update('xbox_key_chain_left', new_value)

    @property
    def xbox_key_chain_right(self) -> str:
        return self.get('xbox_key_chain_right', XboxButtonEnum.RB.value.value)

    @xbox_key_chain_right.setter
    def xbox_key_chain_right(self, new_value: str) -> None:
        self.update('xbox_key_chain_right', new_value)

    @property
    def xbox_key_move_w(self) -> str:
        return self.get('xbox_key_move_w', XboxButtonEnum.L_STICK_W.value.value)

    @xbox_key_move_w.setter
    def xbox_key_move_w(self, new_value: str) -> None:
        self.update('xbox_key_move_w', new_value)

    @property
    def xbox_key_move_s(self) -> str:
        return self.get('xbox_key_move_s', XboxButtonEnum.L_STICK_S.value.value)

    @xbox_key_move_s.setter
    def xbox_key_move_s(self, new_value: str) -> None:
        self.update('xbox_key_move_s', new_value)

    @property
    def xbox_key_move_a(self) -> str:
        return self.get('xbox_key_move_a', XboxButtonEnum.L_STICK_A.value.value)

    @xbox_key_move_a.setter
    def xbox_key_move_a(self, new_value: str) -> None:
        self.update('xbox_key_move_a', new_value)

    @property
    def xbox_key_move_d(self) -> str:
        return self.get('xbox_key_move_d', XboxButtonEnum.L_STICK_D.value.value)

    @xbox_key_move_d.setter
    def xbox_key_move_d(self, new_value: str) -> None:
        self.update('xbox_key_move_d', new_value)

    @property
    def xbox_key_lock(self) -> str:
        return self.get('xbox_key_lock', XboxButtonEnum.R_THUMB.value.value)

    @xbox_key_lock.setter
    def xbox_key_lock(self, new_value: str) -> None:
        self.update('xbox_key_lock', new_value)

    @property
    def xbox_key_chain_cancel(self) -> str:
        return self.get('xbox_key_chain_cancel', XboxButtonEnum.A.value.value)

    @xbox_key_chain_cancel.setter
    def xbox_key_chain_cancel(self, new_value: str) -> None:
        self.update('xbox_key_chain_cancel', new_value)

    @property
    def ds4_key_press_time(self) -> float:
        return self.get('ds4_key_press_time', 0.02)

    @ds4_key_press_time.setter
    def ds4_key_press_time(self, new_value: float) -> None:
        self.update('ds4_key_press_time', new_value)

    @property
    def ds4_key_normal_attack(self) -> str:
        return self.get('ds4_key_normal_attack', Ds4ButtonEnum.SQUARE.value.value)

    @ds4_key_normal_attack.setter
    def ds4_key_normal_attack(self, new_value: str) -> None:
        self.update('ds4_key_normal_attack', new_value)

    @property
    def ds4_key_dodge(self) -> str:
        return self.get('ds4_key_dodge', Ds4ButtonEnum.CROSS.value.value)

    @ds4_key_dodge.setter
    def ds4_key_dodge(self, new_value: str) -> None:
        self.update('ds4_key_dodge', new_value)

    @property
    def ds4_key_switch_next(self) -> str:
        return self.get('ds4_key_switch_next', Ds4ButtonEnum.R1.value.value)

    @ds4_key_switch_next.setter
    def ds4_key_switch_next(self, new_value: str) -> None:
        self.update('ds4_key_switch_next', new_value)

    @property
    def ds4_key_switch_prev(self) -> str:
        return self.get('ds4_key_switch_prev', Ds4ButtonEnum.L1.value.value)

    @ds4_key_switch_prev.setter
    def ds4_key_switch_prev(self, new_value: str) -> None:
        self.update('ds4_key_switch_prev', new_value)

    @property
    def ds4_key_special_attack(self) -> str:
        return self.get('ds4_key_special_attack', Ds4ButtonEnum.TRIANGLE.value.value)

    @ds4_key_special_attack.setter
    def ds4_key_special_attack(self, new_value: str) -> None:
        self.update('ds4_key_special_attack', new_value)

    @property
    def ds4_key_ultimate(self) -> str:
        """爆发技"""
        return self.get('ds4_key_ultimate', Ds4ButtonEnum.R2.value.value)

    @ds4_key_ultimate.setter
    def ds4_key_ultimate(self, new_value: str) -> None:
        self.update('ds4_key_ultimate', new_value)

    @property
    def ds4_key_interact(self) -> str:
        """交互"""
        return self.get('ds4_key_interact', Ds4ButtonEnum.CROSS.value.value)

    @ds4_key_interact.setter
    def ds4_key_interact(self, new_value: str) -> None:
        self.update('ds4_key_interact', new_value)

    @property
    def ds4_key_chain_left(self) -> str:
        return self.get('ds4_key_chain_left', Ds4ButtonEnum.L1.value.value)

    @ds4_key_chain_left.setter
    def ds4_key_chain_left(self, new_value: str) -> None:
        self.update('ds4_key_chain_left', new_value)

    @property
    def ds4_key_chain_right(self) -> str:
        return self.get('ds4_key_chain_right', Ds4ButtonEnum.R1.value.value)

    @ds4_key_chain_right.setter
    def ds4_key_chain_right(self, new_value: str) -> None:
        self.update('ds4_key_chain_right', new_value)

    @property
    def ds4_key_move_w(self) -> str:
        return self.get('ds4_key_move_w', Ds4ButtonEnum.L_STICK_W.value.value)

    @ds4_key_move_w.setter
    def ds4_key_move_w(self, new_value: str) -> None:
        self.update('ds4_key_move_w', new_value)

    @property
    def ds4_key_move_s(self) -> str:
        return self.get('ds4_key_move_s', Ds4ButtonEnum.L_STICK_S.value.value)

    @ds4_key_move_s.setter
    def ds4_key_move_s(self, new_value: str) -> None:
        self.update('ds4_key_move_s', new_value)

    @property
    def ds4_key_move_a(self) -> str:
        return self.get('ds4_key_move_a', Ds4ButtonEnum.L_STICK_A.value.value)

    @ds4_key_move_a.setter
    def ds4_key_move_a(self, new_value: str) -> None:
        self.update('ds4_key_move_a', new_value)

    @property
    def ds4_key_move_d(self) -> str:
        return self.get('ds4_key_move_d', Ds4ButtonEnum.L_STICK_D.value.value)

    @ds4_key_move_d.setter
    def ds4_key_move_d(self, new_value: str) -> None:
        self.update('ds4_key_move_d', new_value)

    @property
    def ds4_key_lock(self) -> str:
        return self.get('ds4_key_lock', Ds4ButtonEnum.R_THUMB.value.value)

    @ds4_key_lock.setter
    def ds4_key_lock(self, new_value: str) -> None:
        self.update('ds4_key_lock', new_value)

    @property
    def ds4_key_chain_cancel(self) -> str:
        return self.get('ds4_key_chain_cancel', Ds4ButtonEnum.CROSS.value.value)

    @ds4_key_chain_cancel.setter
    def ds4_key_chain_cancel(self, new_value: str) -> None:
        self.update('ds4_key_chain_cancel', new_value)

    # ── 后台模式手柄动作键 ───────────────────────────────
    # 每个 GamepadActionEnum 动作对应一个可配置的按键组合。
    # Xbox 和 DS4 各有独立配置，存储值格式: 'xbox_a' / 'ds4_cross' (单键) 或 'xbox_lb+xbox_a' / 'ds4_l1+ds4_cross' (组合键)。

    @property
    def background_gamepad_type(self) -> str:
        return self.get('background_gamepad_type', BackgroundGamepadTypeEnum.XBOX.value.value)

    @background_gamepad_type.setter
    def background_gamepad_type(self, new_value: str) -> None:
        self.update('background_gamepad_type', new_value)

    # ── Xbox 动作键 ──

    @property
    def xbox_action_interact(self) -> str:
        return self.get('xbox_action_interact', 'xbox_x')

    @xbox_action_interact.setter
    def xbox_action_interact(self, new_value: str) -> None:
        self.update('xbox_action_interact', new_value)

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
    def ds4_action_interact(self) -> str:
        return self.get('ds4_action_interact', 'ds4_square')

    @ds4_action_interact.setter
    def ds4_action_interact(self, new_value: str) -> None:
        self.update('ds4_action_interact', new_value)

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
        prefix = gamepad_type  # 'xbox' 或 'ds4'
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
