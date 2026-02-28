from __future__ import annotations

import ctypes
import re
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
_user32.IsIconic.argtypes = [wintypes.HWND]
_user32.IsIconic.restype = wintypes.BOOL
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.IsWindowVisible.restype = wintypes.BOOL

_shcore = None
try:
    _shcore = ctypes.windll.shcore
except Exception:
    _shcore = None

if _shcore is not None:
    _shcore.GetProcessDpiAwareness.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_int)]
    _shcore.GetProcessDpiAwareness.restype = ctypes.c_long

_PROCESS_DPI_UNAWARE = 0
_PROCESS_SYSTEM_DPI_AWARE = 1
_PROCESS_PER_MONITOR_DPI_AWARE = 2


def get_windows_build() -> int:
    if not hasattr(sys, "getwindowsversion"):
        return 0
    return int(sys.getwindowsversion().build)


def is_windows_build_supported(min_build: int = 19041) -> bool:
    return get_windows_build() >= min_build


def get_process_dpi_awareness() -> int:
    if _shcore is None:
        return _PROCESS_DPI_UNAWARE
    awareness = ctypes.c_int(_PROCESS_DPI_UNAWARE)
    hr = _shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
    if hr != 0:
        return _PROCESS_DPI_UNAWARE
    return int(awareness.value)


def is_process_dpi_aware() -> bool:
    return get_process_dpi_awareness() in (
        _PROCESS_SYSTEM_DPI_AWARE,
        _PROCESS_PER_MONITOR_DPI_AWARE,
    )


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


def key_to_vk(key: str) -> int | None:
    key_name = str(key or "").strip().lower()
    if not key_name:
        return None

    vk_match = re.fullmatch(r"vk_(\d+)", key_name)
    if vk_match:
        vk = int(vk_match.group(1))
        if 0 <= vk <= 254:
            return vk
        return None

    if len(key_name) == 1 and key_name.isalnum():
        return ord(key_name.upper())

    if key_name.startswith("numpad_"):
        suffix = key_name.replace("numpad_", "", 1)
        if suffix.isdigit():
            num = int(suffix)
            if 0 <= num <= 9:
                return 0x60 + num

    fn_match = re.fullmatch(r"f(\d{1,2})", key_name)
    if fn_match:
        fn_num = int(fn_match.group(1))
        if 1 <= fn_num <= 24:
            return 0x70 + fn_num - 1

    mapping = {
        "space": 0x20,
        "tab": 0x09,
        "enter": 0x0D,
        "esc": 0x1B,
        "escape": 0x1B,
        "backspace": 0x08,
        "delete": 0x2E,
        "insert": 0x2D,
        "home": 0x24,
        "end": 0x23,
        "page_up": 0x21,
        "page_down": 0x22,
        "up": 0x26,
        "down": 0x28,
        "left": 0x25,
        "right": 0x27,
        "minus": 0xBD,
        "equals": 0xBB,
        "comma": 0xBC,
        "period": 0xBE,
        "slash": 0xBF,
        "backslash": 0xDC,
        "semicolon": 0xBA,
        "apostrophe": 0xDE,
        "grave": 0xC0,
        "l_bracket": 0xDB,
        "r_bracket": 0xDD,
    }
    return mapping.get(key_name)


def is_hotkey_combo_pressed(main_key: str) -> bool:
    main_vk = key_to_vk(main_key)
    if main_vk is None:
        return False
    return is_ctrl_pressed() and is_alt_pressed() and is_key_pressed(main_vk)


def is_window_minimized(hwnd: int | None) -> bool:
    if hwnd is None or int(hwnd) == 0:
        return False
    return bool(_user32.IsIconic(int(hwnd)))


def is_window_visible(hwnd: int | None) -> bool:
    """Check whether a window has the WS_VISIBLE style set."""
    if hwnd is None or int(hwnd) == 0:
        return False
    return bool(_user32.IsWindowVisible(int(hwnd)))


def set_window_click_through(hwnd: int | None, click_through: bool) -> bool:
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


def set_window_display_affinity(hwnd: int | None, exclude_from_capture: bool) -> bool:
    if hwnd is None or int(hwnd) == 0:
        return False

    affinity = WDA_EXCLUDEFROMCAPTURE if exclude_from_capture else WDA_NONE
    return bool(_user32.SetWindowDisplayAffinity(int(hwnd), affinity))
