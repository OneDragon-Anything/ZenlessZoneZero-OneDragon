from concurrent.futures import ThreadPoolExecutor, Future

from pynput import keyboard, mouse
from typing import Callable

from one_dragon.utils import thread_utils

_key_mouse_btn_listener_executor = ThreadPoolExecutor(thread_name_prefix='od_key_mouse_btn_listener', max_workers=8)


class PcButtonListener:

    def __init__(self,
                 on_button_tap: Callable[[str], None],
                 listen_keyboard: bool = False,
                 listen_mouse: bool = False,
                 listen_gamepad: bool = False,
                 ):
        self.keyboard_listener = keyboard.Listener(on_press=self._on_keyboard_press)
        self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self.gamepad_listener = None

        self.on_button_tap: Callable[[str], None] = on_button_tap

        self.listen_keyboard: bool = listen_keyboard
        self.listen_mouse: bool = listen_mouse
        self.listen_gamepad: bool = listen_gamepad

    def _on_keyboard_press(self, event):
        if isinstance(event, keyboard.Key):
            k = event.name
        elif isinstance(event, keyboard.KeyCode):
            # 处理小键盘按键和特殊按键
            if event.char is not None:
                k = event.char
            elif hasattr(event, 'vk') and event.vk is not None:
                # 使用虚拟键码来识别小键盘按键
                k = self._get_numpad_key_name(event.vk)
            elif hasattr(event, 'vk'):
                k = f'vk_{event.vk}'  # vk 为 None 的情况
            else:
                k = 'unknown'  # 没有 vk 属性
        else:
            return

        # 确保按键名称不为空
        if k is None or k == '':
            return

        self._call_button_tap_callback(k)

    def _get_numpad_key_name(self, vk: int) -> str:
        """
        根据虚拟键码获取小键盘按键名称
        :param vk: 虚拟键码
        :return: 按键名称
        """
        # 小键盘数字键: vk 96-105 对应 numpad_0 到 numpad_9
        if 96 <= vk <= 105:
            return f'numpad_{vk - 96}'

        # 其他按键返回通用格式
        return f'vk_{vk}'

    def _on_mouse_click(self, x, y, button: mouse.Button, pressed):
        if pressed == 1:
            self._call_button_tap_callback('mouse_' + button.name)

    def _call_button_tap_callback(self, key: str) -> None:
        if self.on_button_tap is not None:
            future: Future = _key_mouse_btn_listener_executor.submit(self.on_button_tap, key)
            future.add_done_callback(thread_utils.handle_future_result)

    def start(self):
        if self.listen_keyboard:
            self.keyboard_listener.start()
        if self.listen_mouse:
            self.mouse_listener.start()

    def stop(self):
        self.keyboard_listener.stop()
        self.mouse_listener.stop()
