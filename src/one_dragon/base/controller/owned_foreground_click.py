"""前台鼠标输入的目标窗口归属校验。"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pywintypes
import win32con
import win32gui
import win32process


def owns_click_point(hwnd: int, point: tuple[int, int]) -> bool:
    """检查前台窗口和屏幕点击点是否属于目标窗口。

    Args:
        hwnd: 游戏顶层窗口句柄。
        point: 屏幕像素坐标。

    Returns:
        两项归属均匹配时返回 True。
    """
    if not win32gui.IsWindow(hwnd):
        return False
    foreground = win32gui.GetForegroundWindow()
    pixel_window = win32gui.WindowFromPoint(point)
    return bool(
        foreground
        and pixel_window
        and win32gui.GetAncestor(foreground, win32con.GA_ROOT) == hwnd
        and win32gui.GetAncestor(pixel_window, win32con.GA_ROOT) == hwnd
    )


@contextmanager
def owned_foreground_click(
    hwnd: int | None, point: tuple[int, int], activate: Callable[[], bool]
) -> Iterator[Callable[[], bool]]:
    """临时解除遮挡并在输入前校验窗口归属，退出时恢复置顶属性。

    Args:
        hwnd: 游戏顶层窗口句柄，缺失时不允许输入。
        point: 官方操作选定的屏幕坐标。
        activate: 官方窗口激活方法。

    Yields:
        可在移动鼠标后再次调用的归属检查。
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        yield lambda: False
        return
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    if not (left <= point[0] < right and top <= point[1] < bottom):
        yield lambda: False
        return
    identity = win32process.GetWindowThreadProcessId(hwnd)

    def still_owned() -> bool:
        """校验句柄未被销毁或复用。"""
        return (
            win32gui.IsWindow(hwnd)
            and win32process.GetWindowThreadProcessId(hwnd) == identity
        )

    def can_press() -> bool:
        """校验当前输入接收窗口及像素归属。"""
        return still_owned() and owns_click_point(hwnd, point)

    was_topmost = bool(
        win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOPMOST
    )
    raised = False
    flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
    try:
        if not can_press():
            if not was_topmost:
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, flags)
                raised = True
            activate()
        yield can_press
    finally:
        if raised and still_owned():
            try:
                win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            except pywintypes.error:
                if still_owned():
                    raise
