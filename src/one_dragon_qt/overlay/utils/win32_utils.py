from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_MENU = 0x12
VK_LMENU = 0xA4
VK_RMENU = 0xA5

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

WDA_NONE = 0x0
WDA_EXCLUDEFROMCAPTURE = 0x11


_user32 = ctypes.windll.user32

_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetWindowLongW.restype = ctypes.c_long
_user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
_user32.SetWindowLongW.restype = ctypes.c_long
_user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
_user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
_user32.GetAsyncKeyState.restype = ctypes.c_short


def get_windows_build() -> int:
    if not hasattr(sys, "getwindowsversion"):
        return 0
    return int(sys.getwindowsversion().build)


def is_windows_build_supported(min_build: int = 19041) -> bool:
    return get_windows_build() >= min_build


def is_key_pressed(vk: int) -> bool:
    state = _user32.GetAsyncKeyState(vk)
    return bool(state & 0x8000)


def is_ctrl_pressed() -> bool:
    return (
        is_key_pressed(VK_CONTROL)
        or is_key_pressed(VK_LCONTROL)
        or is_key_pressed(VK_RCONTROL)
    )


def is_alt_pressed() -> bool:
    return (
        is_key_pressed(VK_MENU)
        or is_key_pressed(VK_LMENU)
        or is_key_pressed(VK_RMENU)
    )


def set_window_click_through(hwnd: int, click_through: bool) -> bool:
    if hwnd is None or int(hwnd) == 0:
        return False

    old_style = _user32.GetWindowLongW(int(hwnd), GWL_EXSTYLE)
    new_style = old_style | WS_EX_LAYERED
    if click_through:
        new_style |= WS_EX_TRANSPARENT
    else:
        new_style &= ~WS_EX_TRANSPARENT

    ctypes.set_last_error(0)
    result = _user32.SetWindowLongW(int(hwnd), GWL_EXSTYLE, new_style)
    if result == 0 and ctypes.get_last_error() != 0:
        return False
    return True


def set_window_display_affinity(hwnd: int, exclude_from_capture: bool) -> bool:
    if hwnd is None or int(hwnd) == 0:
        return False

    affinity = WDA_EXCLUDEFROMCAPTURE if exclude_from_capture else WDA_NONE
    return bool(_user32.SetWindowDisplayAffinity(int(hwnd), affinity))
