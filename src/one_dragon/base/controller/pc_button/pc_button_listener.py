import sys
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from pynput import keyboard, mouse

from one_dragon.utils import thread_utils

if sys.platform == 'darwin':
    from pynput.keyboard._darwin import Listener as DarwinKeyboardListener
    from pynput.mouse._darwin import Listener as DarwinMouseListener
    from Quartz import (
        CFMachPortCreateRunLoopSource,
        CFRunLoopAddSource,
        CFRunLoopGetCurrent,
        CFRunLoopRunInMode,
        CFRunLoopStop,
        CGEventTapEnable,
        kCFRunLoopDefaultMode,
        kCFRunLoopRunTimedOut,
    )

    class MacListenerMixin:

        def _run(self) -> None:
            self._loop = None
            try:
                tap = self._create_event_tap()
                if tap is None:
                    self._log.warning('无法创建 macOS 输入事件监听器，请检查辅助功能权限')
                    self._mark_ready()
                    return

                loop_source = CFMachPortCreateRunLoopSource(None, tap, 0)
                self._loop = CFRunLoopGetCurrent()
                CFRunLoopAddSource(self._loop, loop_source, kCFRunLoopDefaultMode)
                CGEventTapEnable(tap, True)
                self._mark_ready()

                while self.running:
                    result = CFRunLoopRunInMode(kCFRunLoopDefaultMode, 1, False)
                    if result != kCFRunLoopRunTimedOut:
                        break
            finally:
                self._loop = None

        def _stop_platform(self) -> None:
            if self._loop is not None:
                CFRunLoopStop(self._loop)


    class MacKeyboardListener(MacListenerMixin, DarwinKeyboardListener):
        pass


    class MacMouseListener(MacListenerMixin, DarwinMouseListener):
        pass


class PcButtonListener:

    def __init__(self,
                 on_button_tap: Callable[[str], None],
                 listen_keyboard: bool = False,
                 listen_mouse: bool = False,
                 ):
        if sys.platform == 'darwin':
            self.keyboard_listener = MacKeyboardListener(on_press=self._on_keyboard_press)
            self.mouse_listener = MacMouseListener(on_click=self._on_mouse_click)
        else:
            self.keyboard_listener = keyboard.Listener(on_press=self._on_keyboard_press)
            self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self.on_button_tap: Callable[[str], None] = on_button_tap

        self.listen_keyboard: bool = listen_keyboard
        self.listen_mouse: bool = listen_mouse
        self._executor = ThreadPoolExecutor(thread_name_prefix='od_key_mouse_btn_listener', max_workers=8)

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
            future: Future = self._executor.submit(self.on_button_tap, key)
            future.add_done_callback(thread_utils.handle_future_result)

    def start(self):
        if self.listen_keyboard:
            self.keyboard_listener.start()
        if self.listen_mouse:
            self.mouse_listener.start()

    def stop(self):
        self.keyboard_listener.stop()
        self.mouse_listener.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)
