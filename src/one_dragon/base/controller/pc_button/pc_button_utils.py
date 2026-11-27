from functools import lru_cache

from pynput import keyboard, mouse


@lru_cache
def is_mouse_button(key: str) -> bool:
    """
    是否鼠标按键
    :param key:
    :return:
    """
    return key.startswith('mouse_')


@lru_cache
def get_button(key: str) -> keyboard.KeyCode | keyboard.Key | mouse.Button | str:
    if is_mouse_button(key):
        return get_mouse_button(key)
    return get_keyboard_button(key)


@lru_cache
def get_mouse_button(key: str) -> mouse.Button:
    real_key = key[6:]  # 取mouse_之后的部分
    return mouse.Button[real_key]


@lru_cache
def get_keyboard_button(key: str) -> keyboard.KeyCode | keyboard.Key | str:
    # 处理小键盘数字键: numpad_0 到 numpad_9
    if key.startswith('numpad_') and len(key) == 8 and key[-1].isdigit():
        vk_code = 96 + int(key[-1])  # 小键盘0的虚拟键码是96
        return keyboard.KeyCode.from_vk(vk_code)

    if key in keyboard.Key.__members__:
        return keyboard.Key[key]
    elif len(key) == 1:
        return keyboard.KeyCode.from_char(key)
    else:
        return key
