import threading
import time

from pynput import keyboard, mouse

from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.controller.pc_button.pc_button_controller import PcButtonController


class KeyboardMouseController(PcButtonController):

    def __init__(self):
        PcButtonController.__init__(self)
        self.keyboard = keyboard.Controller()
        self.mouse = mouse.Controller()
        self._pressed_keys: set[str] = set()  # 当前按下的键
        self._pressed_lock: threading.Lock = threading.Lock()  # 多个线程会同时按同一个键

    def tap(self, key: str) -> None:
        """
        按一次按键
        :param key: 按键
        :return:
        """
        if pc_button_utils.is_mouse_button(key):
            self.mouse.click(pc_button_utils.get_mouse_button(key))
        else:
            self.keyboard.tap(pc_button_utils.get_keyboard_button(key))

    def press(self, key: str, press_time: float | None = None) -> None:
        """
        :param key: 按键
        :param press_time: 持续按键时间
        :return:
        """
        is_mouse = pc_button_utils.is_mouse_button(key)
        real_key = pc_button_utils.get_mouse_button(key) if is_mouse else pc_button_utils.get_keyboard_button(key)
        if press_time is None:
            # 先记账再发键：发键那几微秒里别的线程来 release 也不会漏掉
            with self._pressed_lock:
                self._pressed_keys.add(key)
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
        """松开按键。账本只记状态，不再当门禁。

        不管账本里有没有这条键都发 key-up：多发的 key-up 无害，漏发会让按键
        一直卡在按下状态。多个线程同时按同一个键、或者进程中断时，账本和真实
        键态会错开，按账本判断就永远松不掉。
        """
        with self._pressed_lock:
            self._pressed_keys.discard(key)
        is_mouse = pc_button_utils.is_mouse_button(key)
        if is_mouse:
            self.mouse.release(pc_button_utils.get_mouse_button(key))
        else:
            self.keyboard.release(pc_button_utils.get_keyboard_button(key))

    def reset(self) -> None:
        with self._pressed_lock:
            keys = list(self._pressed_keys)
        for key in keys:
            self.release(key)


if __name__ == '__main__':
    _c = KeyboardMouseController()
    t1 = time.time()
    _c.press('a')
    _c.release('a')
    print('%.4f' % (time.time() - t1))
