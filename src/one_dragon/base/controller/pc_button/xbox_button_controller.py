import time

from enum import Enum
from typing import Callable, List, Optional

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.controller.pc_button.pc_button_controller import PcButtonController


class XboxButtonEnum(Enum):

    A = ConfigItem('A', 'xbox_0')
    B = ConfigItem('B', 'xbox_1')
    X = ConfigItem('X', 'xbox_2')
    Y = ConfigItem('Y', 'xbox_3')
    LT = ConfigItem('LT', 'xbox_4')
    RT = ConfigItem('RT', 'xbox_5')
    LB = ConfigItem('LB', 'xbox_6')
    RB = ConfigItem('RB', 'xbox_7')
    L_STICK_W = ConfigItem('左摇杆-上', 'xbox_8')
    L_STICK_S = ConfigItem('左摇杆-下', 'xbox_9')
    L_STICK_A = ConfigItem('左摇杆-左', 'xbox_10')
    L_STICK_D = ConfigItem('左摇杆-右', 'xbox_11')
    L_THUMB = ConfigItem('左摇杆-按下', 'xbox_12')
    R_THUMB = ConfigItem('右摇杆-按下', 'xbox_13')


class XboxButtonController(PcButtonController):

    def __init__(self):
        PcButtonController.__init__(self)
        self.pad = None
        if pc_button_utils.is_vgamepad_installed():
            import vgamepad as vg
            self.pad = vg.VX360Gamepad()
            self._btn = vg.XUSB_BUTTON

        self._tap_handler: List[Callable[[Optional[bool], Optional[float]], None]] = [
            self.tap_a,
            self.tap_b,
            self.tap_x,
            self.tap_y,
            self.tap_lt,
            self.tap_rt,
            self.tap_lb,
            self.tap_rb,
            self.tap_l_stick_w,
            self.tap_l_stick_s,
            self.tap_l_stick_a,
            self.tap_l_stick_d,
            self.tap_l_thumb,
            self.tap_r_thumb,
        ]

        self.release_handler: List[Callable[[], None]] = [
            self.release_a,
            self.release_b,
            self.release_x,
            self.release_y,
            self.release_lt,
            self.release_rt,
            self.release_lb,
            self.release_rb,
            self.release_l_stick,
            self.release_l_stick,
            self.release_l_stick,
            self.release_l_stick,
            self.release_l_thumb,
            self.release_r_thumb,
        ]

    def tap(self, key: str) -> None:
        """
        触发按键
        :param key:
        :return:
        """
        if not self.input_enabled:
            return

        if key is None:  # 部分按键不支持
            return
        self._tap_handler[int(key.split('_')[-1])](False, None)

    def tap_a(self, press: bool = False, press_time: Optional[float] = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_A, press=press, press_time=press_time)

    def tap_b(self, press: bool = False, press_time: Optional[float] = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_B, press=press, press_time=press_time)

    def tap_x(self, press: bool = False, press_time: Optional[float] = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_X, press=press, press_time=press_time)

    def tap_y(self, press: bool = False, press_time: Optional[float] = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_Y, press=press, press_time=press_time)

    def tap_lt(self, press: bool = False, press_time: Optional[float] = None) -> None:
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

    def tap_rt(self, press: bool = False, press_time: Optional[float] = None) -> None:
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

    def tap_lb(self, press: bool = False, press_time: Optional[float] = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_LEFT_SHOULDER, press=press, press_time=press_time)

    def tap_rb(self, press: bool = False, press_time: Optional[float] = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_RIGHT_SHOULDER, press=press, press_time=press_time)

    def tap_l_stick_w(self, press: bool = False, press_time: Optional[float] = None) -> None:
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

    def tap_l_stick_s(self, press: bool = False, press_time: Optional[float] = None) -> None:
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

    def tap_l_stick_a(self, press: bool = False, press_time: Optional[float] = None) -> None:
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

    def tap_l_stick_d(self, press: bool = False, press_time: Optional[float] = None) -> None:
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

    def tap_l_thumb(self, press: bool = False, press_time: Optional[float] = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_LEFT_THUMB, press=press, press_time=press_time)

    def tap_r_thumb(self, press: bool = False, press_time: Optional[float] = None) -> None:
        self._press_button(self._btn.XUSB_GAMEPAD_RIGHT_THUMB, press=press, press_time=press_time)

    def _press_button(self, btn, press: bool = False, press_time: Optional[float] = None):
        """
        :param btn: 按键
        :param press: 是否按下
        :param press_time: 按下时间。如果 press=False press_time=None，则使用key_press_time；如果 press=True press=None 则不放开
        :return:
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

    def press(self, key: str, press_time: Optional[float] = None) -> None:
        if not self.input_enabled:
            return

        if key is None:  # 部分按键不支持
            return
        self._tap_handler[int(key.split('_')[-1])](True, press_time)

    def release(self, key: str) -> None:
        if not self.input_enabled:
            return

        if key is None:  # 部分按键不支持
            return
        self.release_handler[int(key.split('_')[-1])]()

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

    def _release_btn(self, btn) -> None:
        """
        释放具体按键
        """
        self.pad.release_button(btn)
        self.pad.update()
