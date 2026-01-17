import time

from pynput import keyboard, mouse
from typing import Optional

from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.controller.pc_button.pc_button_controller import PcButtonController


class KeyboardMouseController(PcButtonController):

    def __init__(self):
        PcButtonController.__init__(self)
        self.keyboard = keyboard.Controller()
        self.mouse = mouse.Controller()

    def tap(self, key: str) -> None:
        """
        按一次按键
        :param key: 按键
        :return:
        """
        if not self.input_enabled:
            return

        if pc_button_utils.is_mouse_button(key):
            self.mouse.click(pc_button_utils.get_mouse_button(key))
        else:
            self.keyboard.tap(pc_button_utils.get_keyboard_button(key))

    def press(self, key: str, press_time: Optional[float] = None) -> None:
        """
        :param key: 按键
        :param press_time: 持续按键时间
        :return:
        """
        if not self.input_enabled:
            return

        is_mouse = pc_button_utils.is_mouse_button(key)
        real_key = pc_button_utils.get_mouse_button(key) if is_mouse else pc_button_utils.get_keyboard_button(key)
        if is_mouse:
            self.mouse.press(real_key)
        else:
            self.keyboard.press(real_key)

        if press_time is not None:
            time.sleep(press_time)

            if is_mouse:
                self.mouse.release(real_key)
            else:
                self.keyboard.release(real_key)

    def release(self, key: str) -> None:
        is_mouse = pc_button_utils.is_mouse_button(key)
        if is_mouse:
            self.mouse.release(pc_button_utils.get_mouse_button(key))
        else:
            self.keyboard.release(pc_button_utils.get_keyboard_button(key))


if __name__ == '__main__':
    _c = KeyboardMouseController()
    t1 = time.time()
    _c.press('a')
    _c.release('a')
    print('%.4f' % (time.time() - t1))