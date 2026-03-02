import time
from collections.abc import Callable
from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.controller.pc_button.pc_button_controller import PcButtonController


class XboxButtonEnum(Enum):

    A = ConfigItem('A', 'xbox_a')
    B = ConfigItem('B', 'xbox_b')
    X = ConfigItem('X', 'xbox_x')
    Y = ConfigItem('Y', 'xbox_y')
    LT = ConfigItem('LT', 'xbox_lt')
    RT = ConfigItem('RT', 'xbox_rt')
    LB = ConfigItem('LB', 'xbox_lb')
    RB = ConfigItem('RB', 'xbox_rb')
    L_STICK_W = ConfigItem('左摇杆-上', 'xbox_ls_up')
    L_STICK_S = ConfigItem('左摇杆-下', 'xbox_ls_down')
    L_STICK_A = ConfigItem('左摇杆-左', 'xbox_ls_left')
    L_STICK_D = ConfigItem('左摇杆-右', 'xbox_ls_right')
    L_THUMB = ConfigItem('左摇杆-按下', 'xbox_l_thumb')
    R_THUMB = ConfigItem('右摇杆-按下', 'xbox_r_thumb')
    DPAD_UP = ConfigItem('十字键-上', 'xbox_dpad_up')
    DPAD_DOWN = ConfigItem('十字键-下', 'xbox_dpad_down')
    DPAD_LEFT = ConfigItem('十字键-左', 'xbox_dpad_left')
    DPAD_RIGHT = ConfigItem('十字键-右', 'xbox_dpad_right')
    START = ConfigItem('START', 'xbox_start')
    BACK = ConfigItem('BACK', 'xbox_back')
    R_STICK_W = ConfigItem('右摇杆-上', 'xbox_rs_up')
    R_STICK_S = ConfigItem('右摇杆-下', 'xbox_rs_down')
    R_STICK_A = ConfigItem('右摇杆-左', 'xbox_rs_left')
    R_STICK_D = ConfigItem('右摇杆-右', 'xbox_rs_right')
    GUIDE = ConfigItem('GUIDE', 'xbox_guide')


class XboxButtonController(PcButtonController):

    def __init__(self):
        PcButtonController.__init__(self)
        self.pad = None
        if pc_button_utils.is_vgamepad_installed():
            import vgamepad as vg
            self.pad = vg.VX360Gamepad()
            self._btn = vg.XUSB_BUTTON

        self._tap_handler: dict[str, Callable[[bool, float | None], None]] = {
            'xbox_a': self.tap_a,
            'xbox_b': self.tap_b,
            'xbox_x': self.tap_x,
            'xbox_y': self.tap_y,
            'xbox_lt': self.tap_lt,
            'xbox_rt': self.tap_rt,
            'xbox_lb': self.tap_lb,
            'xbox_rb': self.tap_rb,
            'xbox_ls_up': self.tap_l_stick_w,
            'xbox_ls_down': self.tap_l_stick_s,
            'xbox_ls_left': self.tap_l_stick_a,
            'xbox_ls_right': self.tap_l_stick_d,
            'xbox_l_thumb': self.tap_l_thumb,
            'xbox_r_thumb': self.tap_r_thumb,
            'xbox_dpad_up': self.tap_dpad_up,
            'xbox_dpad_down': self.tap_dpad_down,
            'xbox_dpad_left': self.tap_dpad_left,
            'xbox_dpad_right': self.tap_dpad_right,
            'xbox_start': self.tap_start,
            'xbox_back': self.tap_back,
            'xbox_rs_up': self.tap_r_stick_w,
            'xbox_rs_down': self.tap_r_stick_s,
            'xbox_rs_left': self.tap_r_stick_a,
            'xbox_rs_right': self.tap_r_stick_d,
            'xbox_guide': self.tap_guide,
        }

        self.release_handler: dict[str, Callable[[], None]] = {
            'xbox_a': self.release_a,
            'xbox_b': self.release_b,
            'xbox_x': self.release_x,
            'xbox_y': self.release_y,
            'xbox_lt': self.release_lt,
            'xbox_rt': self.release_rt,
            'xbox_lb': self.release_lb,
            'xbox_rb': self.release_rb,
            'xbox_ls_up': self.release_l_stick,
            'xbox_ls_down': self.release_l_stick,
            'xbox_ls_left': self.release_l_stick,
            'xbox_ls_right': self.release_l_stick,
            'xbox_l_thumb': self.release_l_thumb,
            'xbox_r_thumb': self.release_r_thumb,
            'xbox_dpad_up': self.release_dpad_up,
            'xbox_dpad_down': self.release_dpad_down,
            'xbox_dpad_left': self.release_dpad_left,
            'xbox_dpad_right': self.release_dpad_right,
            'xbox_start': self.release_start,
            'xbox_back': self.release_back,
            'xbox_rs_up': self.release_r_stick,
            'xbox_rs_down': self.release_r_stick,
            'xbox_rs_left': self.release_r_stick,
            'xbox_rs_right': self.release_r_stick,
            'xbox_guide': self.release_guide,
        }

    def tap(self, key: str) -> None:
        """触发按键。

        Args:
            key: 按键标识。
        """
        if key is None:  # 部分按键不支持
            return
        self._tap_handler[key](False, None)

    def tap_a(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_A, press=press, press_time=press_time)

    def tap_b(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_B, press=press, press_time=press_time)

    def tap_x(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_X, press=press, press_time=press_time)

    def tap_y(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_Y, press=press, press_time=press_time)

    def tap_lt(self, press: bool = False, press_time: float | None = None) -> None:
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

    def tap_rt(self, press: bool = False, press_time: float | None = None) -> None:
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

    def tap_lb(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_LEFT_SHOULDER, press=press, press_time=press_time)

    def tap_rb(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_RIGHT_SHOULDER, press=press, press_time=press_time)

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
        self._press_button(self._btn.XUSB_GAMEPAD_LEFT_THUMB, press=press, press_time=press_time)

    def tap_r_thumb(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_RIGHT_THUMB, press=press, press_time=press_time)

    def tap_dpad_up(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_DPAD_UP, press=press, press_time=press_time)

    def tap_dpad_down(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_DPAD_DOWN, press=press, press_time=press_time)

    def tap_dpad_left(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_DPAD_LEFT, press=press, press_time=press_time)

    def tap_dpad_right(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_DPAD_RIGHT, press=press, press_time=press_time)

    def tap_start(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_START, press=press, press_time=press_time)

    def tap_back(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_BACK, press=press, press_time=press_time)

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

    def tap_guide(self, press: bool = False, press_time: float | None = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_GUIDE, press=press, press_time=press_time)

    def _press_button(self, btn, press: bool = False, press_time: float | None = None):
        """按下按钮。

        Args:
            btn: 按键。
            press: 是否按下。
            press_time: 按下时间。如果 press=False press_time=None，则使用key_press_time；如果 press=True press_time=None 则不放开。
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
        if key is None:  # 部分按键不支持
            return
        self._tap_handler[key](True, press_time)

    def release(self, key: str) -> None:
        if key is None:  # 部分按键不支持
            return
        self.release_handler[key]()

    def release_a(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_A)

    def release_b(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_B)

    def release_x(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_X)

    def release_y(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_Y)

    def release_lt(self) -> None:
        self.pad.left_trigger(value=0)
        self.pad.update()

    def release_rt(self) -> None:
        self.pad.right_trigger(value=0)
        self.pad.update()

    def release_lb(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_LEFT_SHOULDER)

    def release_rb(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_RIGHT_SHOULDER)

    def release_l_stick(self) -> None:
        self.pad.left_joystick_float(0, 0)
        self.pad.update()

    def release_l_thumb(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_LEFT_THUMB)

    def release_r_thumb(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_RIGHT_THUMB)

    def release_dpad_up(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_DPAD_UP)

    def release_dpad_down(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_DPAD_DOWN)

    def release_dpad_left(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_DPAD_LEFT)

    def release_dpad_right(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_DPAD_RIGHT)

    def release_start(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_START)

    def release_back(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_BACK)

    def release_r_stick(self) -> None:
        self.pad.right_joystick_float(0, 0)
        self.pad.update()

    def release_guide(self) -> None:
        self._release_btn(self._btn.XUSB_GAMEPAD_GUIDE)

    def _release_btn(self, btn) -> None:
        """释放具体按键。"""
        self.pad.release_button(btn)
        self.pad.update()
