import time
from collections.abc import Callable
from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.controller.pc_button.pc_button_controller import PcButtonController


class Ds4ButtonEnum(Enum):

    CROSS = ConfigItem('✕', 'ds4_cross')
    CIRCLE = ConfigItem('○', 'ds4_circle')
    SQUARE = ConfigItem('□', 'ds4_square')
    TRIANGLE = ConfigItem('△', 'ds4_triangle')
    L2 = ConfigItem('L2', 'ds4_l2')
    R2 = ConfigItem('R2', 'ds4_r2')
    L1 = ConfigItem('L1', 'ds4_l1')
    R1 = ConfigItem('R1', 'ds4_r1')
    L_STICK_W = ConfigItem('左摇杆-上', 'ds4_ls_up')
    L_STICK_S = ConfigItem('左摇杆-下', 'ds4_ls_down')
    L_STICK_A = ConfigItem('左摇杆-左', 'ds4_ls_left')
    L_STICK_D = ConfigItem('左摇杆-右', 'ds4_ls_right')
    L_THUMB = ConfigItem('左摇杆-按下', 'ds4_l_thumb')
    R_THUMB = ConfigItem('右摇杆-按下', 'ds4_r_thumb')
    DPAD_UP = ConfigItem('十字键-上', 'ds4_dpad_up')
    DPAD_DOWN = ConfigItem('十字键-下', 'ds4_dpad_down')
    DPAD_LEFT = ConfigItem('十字键-左', 'ds4_dpad_left')
    DPAD_RIGHT = ConfigItem('十字键-右', 'ds4_dpad_right')
    OPTIONS = ConfigItem('OPTIONS', 'ds4_options')
    SHARE = ConfigItem('SHARE', 'ds4_share')
    R_STICK_W = ConfigItem('右摇杆-上', 'ds4_rs_up')
    R_STICK_S = ConfigItem('右摇杆-下', 'ds4_rs_down')
    R_STICK_A = ConfigItem('右摇杆-左', 'ds4_rs_left')
    R_STICK_D = ConfigItem('右摇杆-右', 'ds4_rs_right')
    PS = ConfigItem('PS', 'ds4_ps')


class Ds4ButtonController(PcButtonController):

    def __init__(self):
        PcButtonController.__init__(self)
        self.pad = None
        if pc_button_utils.is_vgamepad_installed():
            import vgamepad as vg
            self.pad = vg.VDS4Gamepad()
            self._btn = vg.DS4_BUTTONS
            self._dpad = vg.DS4_DPAD_DIRECTIONS
            self._special = vg.DS4_SPECIAL_BUTTONS

        self._tap_handler: dict[str, Callable[[bool, float | None], None]] = {
            'ds4_cross': self.tap_cross,
            'ds4_circle': self.tap_circle,
            'ds4_square': self.tap_square,
            'ds4_triangle': self.tap_triangle,
            'ds4_l2': self.tap_l2,
            'ds4_r2': self.tap_r2,
            'ds4_l1': self.tap_l1,
            'ds4_r1': self.tap_r1,
            'ds4_ls_up': self.tap_l_stick_w,
            'ds4_ls_down': self.tap_l_stick_s,
            'ds4_ls_left': self.tap_l_stick_a,
            'ds4_ls_right': self.tap_l_stick_d,
            'ds4_l_thumb': self.tap_l_thumb,
            'ds4_r_thumb': self.tap_r_thumb,
            'ds4_dpad_up': self.tap_dpad_up,
            'ds4_dpad_down': self.tap_dpad_down,
            'ds4_dpad_left': self.tap_dpad_left,
            'ds4_dpad_right': self.tap_dpad_right,
            'ds4_options': self.tap_options,
            'ds4_share': self.tap_share,
            'ds4_rs_up': self.tap_r_stick_w,
            'ds4_rs_down': self.tap_r_stick_s,
            'ds4_rs_left': self.tap_r_stick_a,
            'ds4_rs_right': self.tap_r_stick_d,
            'ds4_ps': self.tap_ps,
        }

        self.release_handler: dict[str, Callable[[], None]] = {
            'ds4_cross': self.release_cross,
            'ds4_circle': self.release_circle,
            'ds4_square': self.release_square,
            'ds4_triangle': self.release_triangle,
            'ds4_l2': self.release_l2,
            'ds4_r2': self.release_r2,
            'ds4_l1': self.release_l1,
            'ds4_r1': self.release_r1,
            'ds4_ls_up': self.release_l_stick,
            'ds4_ls_down': self.release_l_stick,
            'ds4_ls_left': self.release_l_stick,
            'ds4_ls_right': self.release_l_stick,
            'ds4_l_thumb': self.release_l_thumb,
            'ds4_r_thumb': self.release_r_thumb,
            'ds4_dpad_up': self.release_dpad,
            'ds4_dpad_down': self.release_dpad,
            'ds4_dpad_left': self.release_dpad,
            'ds4_dpad_right': self.release_dpad,
            'ds4_options': self.release_options,
            'ds4_share': self.release_share,
            'ds4_rs_up': self.release_r_stick,
            'ds4_rs_down': self.release_r_stick,
            'ds4_rs_left': self.release_r_stick,
            'ds4_rs_right': self.release_r_stick,
            'ds4_ps': self.release_ps,
        }

    def tap(self, key: str) -> None:
        """触发按键。"""
        if key is None:  # 部分按键不支持
            return
        self._tap_handler[key](False, None)

    def tap_cross(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.DS4_BUTTON_CROSS, press=press, press_time=press_time)

    def tap_circle(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.DS4_BUTTON_CIRCLE, press=press, press_time=press_time)

    def tap_square(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.DS4_BUTTON_SQUARE, press=press, press_time=press_time)

    def tap_triangle(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.DS4_BUTTON_TRIANGLE, press=press, press_time=press_time)

    def tap_l2(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.left_trigger(value=255)
        self.pad.update()

        if press:
            if press_time is None:  # 不放开
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.left_trigger(value=0)
        self.pad.update()

    def tap_r2(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.right_trigger(value=255)
        self.pad.update()

        if press:
            if press_time is None:  # 不放开
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.right_trigger(value=0)
        self.pad.update()

    def tap_l1(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.DS4_BUTTON_SHOULDER_LEFT, press=press, press_time=press_time)

    def tap_r1(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.DS4_BUTTON_SHOULDER_RIGHT, press=press, press_time=press_time)

    def tap_l_stick_w(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.left_joystick_float(0, 1)
        self.pad.update()

        if press:
            if press_time is None:  # 不放开
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.left_joystick_float(0, 0)
        self.pad.update()

    def tap_l_stick_s(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.left_joystick_float(0, -1)
        self.pad.update()

        if press:
            if press_time is None:  # 不放开
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.left_joystick_float(0, 0)
        self.pad.update()

    def tap_l_stick_a(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.left_joystick_float(-1, 0)
        self.pad.update()

        if press:
            if press_time is None:  # 不放开
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.left_joystick_float(0, 0)
        self.pad.update()

    def tap_l_stick_d(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.left_joystick_float(1, 0)
        self.pad.update()

        if press:
            if press_time is None:  # 不放开
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.left_joystick_float(0, 0)
        self.pad.update()

    def tap_l_thumb(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.DS4_BUTTON_THUMB_LEFT, press=press, press_time=press_time)

    def tap_r_thumb(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.DS4_BUTTON_THUMB_RIGHT, press=press, press_time=press_time)

    def tap_dpad_up(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.directional_pad(direction=self._dpad.DS4_BUTTON_DPAD_NORTH)
        self.pad.update()

        if press:
            if press_time is None:
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.directional_pad(direction=self._dpad.DS4_BUTTON_DPAD_NONE)
        self.pad.update()

    def tap_dpad_down(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.directional_pad(direction=self._dpad.DS4_BUTTON_DPAD_SOUTH)
        self.pad.update()

        if press:
            if press_time is None:
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.directional_pad(direction=self._dpad.DS4_BUTTON_DPAD_NONE)
        self.pad.update()

    def tap_dpad_left(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.directional_pad(direction=self._dpad.DS4_BUTTON_DPAD_WEST)
        self.pad.update()

        if press:
            if press_time is None:
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.directional_pad(direction=self._dpad.DS4_BUTTON_DPAD_NONE)
        self.pad.update()

    def tap_dpad_right(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.directional_pad(direction=self._dpad.DS4_BUTTON_DPAD_EAST)
        self.pad.update()

        if press:
            if press_time is None:
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.directional_pad(direction=self._dpad.DS4_BUTTON_DPAD_NONE)
        self.pad.update()

    def tap_options(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.DS4_BUTTON_OPTIONS, press=press, press_time=press_time)

    def tap_share(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.DS4_BUTTON_SHARE, press=press, press_time=press_time)

    def tap_r_stick_w(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.right_joystick_float(0, 1)
        self.pad.update()

        if press:
            if press_time is None:
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.right_joystick_float(0, 0)
        self.pad.update()

    def tap_r_stick_s(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.right_joystick_float(0, -1)
        self.pad.update()

        if press:
            if press_time is None:
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.right_joystick_float(0, 0)
        self.pad.update()

    def tap_r_stick_a(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.right_joystick_float(-1, 0)
        self.pad.update()

        if press:
            if press_time is None:
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.right_joystick_float(0, 0)
        self.pad.update()

    def tap_r_stick_d(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.right_joystick_float(1, 0)
        self.pad.update()

        if press:
            if press_time is None:
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.right_joystick_float(0, 0)
        self.pad.update()

    def tap_ps(self, press: bool = False, press_time: float | None = None) -> None:
        self.pad.press_special_button(special_button=self._special.DS4_SPECIAL_BUTTON_PS)
        self.pad.update()

        if press:
            if press_time is None:
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.release_special_button(special_button=self._special.DS4_SPECIAL_BUTTON_PS)
        self.pad.update()

    def _press_button(self, btn, press: bool = False, press_time: float | None = None):
        """按键。

        Args:
            btn: 键
            press: 是否按下
            press_time: 按下时间。如果 press=False press_time=None，则使用key_press_time；如果 press=True press=None 则不放开
        """
        self.pad.press_button(btn)
        self.pad.update()

        if press:
            if press_time is None:  # 不放开
                return
        else:
            if press_time is None:
                press_time = self.key_press_time

        time.sleep(max(self.key_press_time, press_time))
        self.pad.release_button(btn)
        self.pad.update()

    def reset(self):
        self.pad.reset()
        self.pad.update()

    def press(self, key: str, press_time: float | None = None) -> None:
        """按键。

        Args:
            key: 按键
            press_time: 持续按键时间
        """
        if key is None:  # 部分按键不支持
            return
        self._tap_handler[key](True, press_time)

    def release(self, key: str) -> None:
        if key is None:  # 部分按键不支持
            return
        self.release_handler[key]()

    def release_cross(self) -> None:
        self._release_btn(self._btn.DS4_BUTTON_CROSS)

    def release_circle(self) -> None:
        self._release_btn(self._btn.DS4_BUTTON_CIRCLE)

    def release_square(self) -> None:
        self._release_btn(self._btn.DS4_BUTTON_SQUARE)

    def release_triangle(self) -> None:
        self._release_btn(self._btn.DS4_BUTTON_TRIANGLE)

    def release_l2(self) -> None:
        self.pad.left_trigger(value=0)
        self.pad.update()

    def release_r2(self) -> None:
        self.pad.right_trigger(value=0)
        self.pad.update()

    def release_l1(self) -> None:
        self._release_btn(self._btn.DS4_BUTTON_SHOULDER_LEFT)

    def release_r1(self) -> None:
        self._release_btn(self._btn.DS4_BUTTON_SHOULDER_RIGHT)

    def release_l_stick(self) -> None:
        self.pad.left_joystick_float(0, 0)
        self.pad.update()

    def release_l_thumb(self) -> None:
        self._release_btn(self._btn.DS4_BUTTON_THUMB_LEFT)

    def release_r_thumb(self) -> None:
        self._release_btn(self._btn.DS4_BUTTON_THUMB_RIGHT)

    def release_dpad(self) -> None:
        self.pad.directional_pad(direction=self._dpad.DS4_BUTTON_DPAD_NONE)
        self.pad.update()

    def release_options(self) -> None:
        self._release_btn(self._btn.DS4_BUTTON_OPTIONS)

    def release_share(self) -> None:
        self._release_btn(self._btn.DS4_BUTTON_SHARE)

    def release_r_stick(self) -> None:
        self.pad.right_joystick_float(0, 0)
        self.pad.update()

    def release_ps(self) -> None:
        self.pad.release_special_button(special_button=self._special.DS4_SPECIAL_BUTTON_PS)
        self.pad.update()

    def _release_btn(self, btn) -> None:
        """释放具体按键。"""
        self.pad.release_button(btn)
        self.pad.update()
