from functools import lru_cache
from pynput import keyboard, mouse
from typing import Union

try:
    import vgamepad
    _VGAMEPAD_INSTALLED = True
except Exception:
    _VGAMEPAD_INSTALLED = False


@lru_cache
def is_mouse_button(key: str) -> bool:
    """
    是否鼠标按键
    :param key:
    :return:
    """
    return key.startswith('mouse_')


@lru_cache
def is_xbox_button(key: str) -> bool:
    """
    是否xbox按键
    :param key:
    :return:
    """
    return key.startswith('xbox_')


@lru_cache
def is_ds4_button(key: str) -> bool:
    """
    是否ds4按键
    :param key:
    :return:
    """
    return key.startswith('ds4_')


@lru_cache
def get_button(key: str):
    if is_mouse_button(key):
        return get_mouse_button(key)
    else:
        return get_keyboard_button(key)


@lru_cache
def get_mouse_button(key: str) -> mouse.Button:
    real_key = key[6:]  # 取mouse_之后的部分
    return mouse.Button[real_key]


@lru_cache
def get_keyboard_button(key: str) -> Union[keyboard.KeyCode, keyboard.Key, str]:
    # 处理小键盘按键
    if key.startswith('numpad_'):
        numpad_name = key[7:]  # 去除 'numpad_' 前缀
        if numpad_name.isdigit():
            # 小键盘数字键 (0-9)
            vk_code = 96 + int(numpad_name)  # 小键盘0的虚拟键码是96
            return keyboard.KeyCode.from_vk(vk_code)
        else:
            # 小键盘运算符
            numpad_operators = {
                'multiply': 106,     # *
                'add': 107,          # +
                'separator': 108,    # 分隔符
                'subtract': 109,     # -
                'decimal': 110,      # .
                'divide': 111,       # /
            }
            if numpad_name in numpad_operators:
                return keyboard.KeyCode.from_vk(numpad_operators[numpad_name])
    
    # 原有逻辑
    if key in keyboard.Key.__members__:
        return keyboard.Key[key]
    elif len(key) == 1:
        return keyboard.KeyCode.from_char(key)
    else:
        return key


@lru_cache
def is_vgamepad_installed() -> bool:
    """
    是否安装了虚拟手柄库
    :return:
    """
    return _VGAMEPAD_INSTALLED
