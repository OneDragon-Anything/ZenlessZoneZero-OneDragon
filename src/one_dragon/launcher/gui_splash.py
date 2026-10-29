"""GUI 模式启动图收尾器。

launcher exe 通过 PyInstaller ``--splash`` 打包：双击 exe 后，bootloader 在
自解压/提权重启阶段于屏幕中央显示启动图（assets/ui/splash_f9.png）——这是
用户看到的第一毫秒反馈，早于任何 Python 代码。本模块只负责启动图的收尾：

- :func:`start` 在 GUI 模式入口拉起后台线程，轮询 EnumWindows 探测 GUI
  主窗口是否就绪，就绪后调用 ``pyi_splash.close()`` 收掉启动图，
  实现「启动图 → GUI」的无缝衔接；
- :func:`close_bootloader_splash` 供控制台模式入口直接调用：控制台窗口
  即将顶上，无需等 GUI 探测，立即收图避免残留；
- :func:`hide_console_window` 在 GUI 模式入口隐藏控制台黑窗（与
  RuntimeLauncher._hide_console 同款实现）；
- 探测超时或任何异常均静默退出并兜底收图：绝不影响启动主流程，
  也绝不让启动图残留在屏幕上。

设计约束：launcher 进程会在 UAC 提权重启后运行本模块（非管理员实例走
``pyuac.runAsAdmin`` 分支直接退出，不会到达 GUI 模式），因此收尾线程
只会启动一次。
"""

from __future__ import annotations

import contextlib
import ctypes
import threading
import time
from ctypes import wintypes

# GUI 主窗口标题 = gt(project_name) + ' ' + 实例名：
# 中文环境为「绝区零 一条龙 01」，英文环境为「ZenlessZoneZero-OneDragon 01」，
# 探测时必须同时兼容两种文案。
GUI_WINDOW_TITLE_KEYWORDS: tuple[str, ...] = (
    'ZenlessZoneZero-OneDragon',
    '绝区零 一条龙',
)

# GUI 冷启动（依赖校验、资源加载等）耗时可达 3 分钟以上，探测超时须留足余量
DEFAULT_GUI_READY_TIMEOUT_SECONDS: float = 420.0

# 探测轮询间隔：远小于人眼可感知的迟滞，同时避免空转占用 CPU
_POLL_INTERVAL_SECONDS: float = 0.4

# EnumWindows 回调签名：BOOL CALLBACK(HWND hwnd, LPARAM lParam)
_EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_user32 = ctypes.windll.user32
_user32.EnumWindows.argtypes = [_EnumWindowsProc, wintypes.LPARAM]
_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

# ShowWindow 命令：隐藏（Win32 SW_HIDE 常量）
_SW_HIDE = 0

_kernel32 = ctypes.windll.kernel32
_kernel32.GetConsoleWindow.restype = wintypes.HWND

# start() 幂等护栏：launcher 生命周期内只允许启动一次收尾线程
_start_guard = threading.Event()


def _find_gui_window(title_keywords: tuple[str, ...]) -> bool:
    """探测 GUI 主窗口是否已经出现。

    :param title_keywords: 主窗口标题关键词集合，任一命中即视为就绪
    :return: 找到就绪的 GUI 主窗口返回 True，否则 False
    """
    matches: list[wintypes.HWND] = []

    def _enum_callback(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        """EnumWindows 回调：跳过不可见/无标题窗口，命中关键词即记下并短路。"""
        if not _user32.IsWindowVisible(hwnd):
            return True
        title_length = _user32.GetWindowTextLengthW(hwnd)
        if title_length <= 0:
            return True
        title_buffer = ctypes.create_unicode_buffer(title_length + 1)
        _user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)
        if any(keyword in title_buffer.value for keyword in title_keywords):
            matches.append(hwnd)
            return False
        return True

    _user32.EnumWindows(_EnumWindowsProc(_enum_callback), 0)
    return bool(matches)


def _close_splash_when_gui_ready(
    title_keywords: tuple[str, ...],
    timeout: float,
) -> None:
    """收尾线程主体：轮询等待 GUI 主窗口就绪，然后收掉 bootloader 启动图。

    无论就绪、超时还是异常退出，都兜底调用 :func:`close_bootloader_splash`，
    确保启动图不残留。
    """
    deadline = time.monotonic() + timeout
    with contextlib.suppress(Exception):
        while time.monotonic() < deadline:
            if _find_gui_window(title_keywords):
                break
            time.sleep(_POLL_INTERVAL_SECONDS)
    close_bootloader_splash()


def hide_console_window() -> None:
    """隐藏控制台窗口，用于 GUI 模式（与 RuntimeLauncher._hide_console 同款）。

    launcher 以 console 子系统打包，双击启动会带出黑窗；GUI 模式在入口处
    将其隐藏。一条龙模式需要控制台输出运行日志、-v 的输出会被其他程序
    读取，均不调用本函数，保持原有控制台行为。
    """
    console_hwnd = _kernel32.GetConsoleWindow()
    if console_hwnd:
        _user32.ShowWindow(console_hwnd, _SW_HIDE)


def close_bootloader_splash() -> None:
    """关闭 PyInstaller ``--splash`` 启动图（若存在）。

    ``pyi_splash`` 仅存在于 PyInstaller 打包环境；源码/venv 运行时 import
    失败属预期，静默跳过。
    """
    with contextlib.suppress(Exception):
        import pyi_splash

        pyi_splash.close()


def start(
    title_keywords: tuple[str, ...] = GUI_WINDOW_TITLE_KEYWORDS,
    timeout: float = DEFAULT_GUI_READY_TIMEOUT_SECONDS,
) -> None:
    """启动启动图收尾线程（非阻塞，幂等）。

    :param title_keywords: 主窗口标题关键词集合，任一命中即视为 GUI 就绪
    :param timeout: 探测兜底超时秒数，超时后强制收图
    """
    if _start_guard.is_set():
        return
    _start_guard.set()
    threading.Thread(
        target=_close_splash_when_gui_ready,
        args=(title_keywords, timeout),
        daemon=True,
        name='gui-splash-watchdog',
    ).start()
