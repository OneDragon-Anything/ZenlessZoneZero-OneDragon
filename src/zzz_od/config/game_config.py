from enum import Enum

from one_dragon.base.config.basic_game_config import BasicGameConfig
from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.controller.pc_button.ds4_button_controller import Ds4ButtonEnum
from one_dragon.base.controller.pc_button.xbox_button_controller import XboxButtonEnum


class GamepadTypeEnum(Enum):

    NONE = ConfigItem('无', 'none')
    XBOX = ConfigItem('Xbox', 'xbox')
    DS4 = ConfigItem('DS4', 'ds4')


class GameConfig(BasicGameConfig):

    @property
    def key_normal_attack(self) -> str:
        return self.get('key_normal_attack', 'mouse_left')

    @key_normal_attack.setter
    def key_normal_attack(self, new_value: str) -> None:
        self.update('key_normal_attack', new_value)

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
