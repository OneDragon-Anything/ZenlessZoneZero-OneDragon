import ctypes
from ctypes.wintypes import RECT
from typing import Optional

import pyautogui
import win32ui
from pygetwindow import Win32Window

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log


class PcGameWindow:

    def __init__(self, win_title: str,
                 standard_width: int = 1920,
                 standard_height: int = 1080):
        self.win_title: str = win_title
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height
        self.standard_game_rect: Rect = Rect(0, 0, standard_width, standard_height)

        self._win: Optional[Win32Window] = None
        self._hWnd = None

        self.init_win()

    def init_win(self) -> None:
        """
        初始化窗口
        :return:
        """
        windows = pyautogui.getWindowsWithTitle(self.win_title)
        if len(windows) > 0:
            for win in windows:
                if win.title == self.win_title:
                    self._win = win
                    self._hWnd = win._hWnd
        else:
            self._win = None
            self._hWnd = None

    def get_win(self) -> Optional[Win32Window]:
        if self._win is None:
            self.init_win()
        return self._win

    def get_hwnd(self) -> int:
        if self._hWnd is None:
            self.init_win()
        return self._hWnd

    @property
    def is_win_valid(self) -> bool:
        """
        当前窗口是否正常
        :return:
        """
        win = self.get_win()
        hwnd = self.get_hwnd()
        return win is not None and hwnd is not None and ctypes.windll.user32.IsWindow(hwnd) != 0

    @property
    def is_win_active(self) -> bool:
        """
        是否当前激活的窗口
        :return:
        """
        win = self.get_win()
        return win.isActive if win is not None else False

    @property
    def is_win_scale(self) -> bool:
        """
        当前窗口是否缩放
        :return:
        """
        win_rect = self.win_rect
        if win_rect is None:
            return False
        else:
            return not (win_rect.width == self.standard_width and win_rect.height == self.standard_height)

    def active(self) -> bool:
        """
        显示并激活当前窗口
        :return:
        """
        win = self.get_win()
        if win is None:
            return False
        if self.is_win_active:
            return True
        try:
            try:
                win.restore()
                win.activate()
                return True
            except win32ui.error as e:
                if e.args[0].find('1400') > 0:  # Invalid window handle
                    log.warning("无效的窗口句柄，尝试重置窗口")
                    self._win = None
                else:
                    log.error("截图失败", exc_info=True)
                return None
            except Exception as e:
                if e.args[0].find('1400') > 0:  # Invalid window handle
                    log.warning("无效的窗口句柄，尝试重置窗口")
                    self._win = None
                    return False
                else:
                    # 比较神奇的一个bug 直接activate有可能失败
                    # https://github.com/asweigart/PyGetWindow/issues/16#issuecomment-1110207862
                    win.minimize()
                    win.restore()
                    win.activate()
                return True
        except Exception:
            log.error('切换到游戏窗口失败', exc_info=True)
            return False

    @property
    def win_rect(self) -> Optional[Rect]:
        """
        获取游戏窗口在桌面上面的位置
        Win32Window 里是整个window的信息 参考源码获取里面client部分的
        :return: 游戏窗口信息
        """
        hwnd = self.get_hwnd()
        if hwnd is None:
            return None
        client_rect = RECT()
        ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(client_rect))
        left_top_pos = ctypes.wintypes.POINT(client_rect.left, client_rect.top)
        ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(left_top_pos))
        return Rect(left_top_pos.x, left_top_pos.y, left_top_pos.x + client_rect.right, left_top_pos.y + client_rect.bottom)

    def get_scaled_game_pos(self, game_pos: Point) -> Optional[Point]:
        """
        获取当前分辨率下游戏窗口里的坐标
        :param game_pos: 默认分辨率下的游戏窗口里的坐标
        :return: 当前分辨率下的游戏窗口里坐标
        """
        win = self.get_win()
        if win is None:
            return None
        rect = self.win_rect
        xs = 1 if rect.width == self.standard_width else rect.width * 1.0 / self.standard_width
        ys = 1 if rect.height == self.standard_height else rect.height * 1.0 / self.standard_height
        s_pos = Point(game_pos.x * xs, game_pos.y * ys)
        return s_pos if self.is_valid_game_pos(game_pos, self.standard_game_rect) else None

    def is_valid_game_pos(self, s_pos: Point, rect: Rect = None) -> bool:
        """
        判断游戏中坐标是否在游戏窗口内
        :param s_pos: 游戏中坐标 已经缩放
        :param rect: 窗口位置信息
        :return: 是否在游戏窗口内
        """
        if rect is None:
            rect = self.standard_game_rect
        return 0 <= s_pos.x < rect.width and 0 <= s_pos.y < rect.height

    def game2win_pos(self, game_pos: Point) -> Optional[Point]:
        """
        获取在屏幕中的坐标
        :param game_pos: 默认分辨率下的游戏窗口里的坐标
        :return: 当前分辨率下的屏幕中的坐标
        """
        rect = self.win_rect
        if rect is None:
            return None
        gp: Point = self.get_scaled_game_pos(game_pos)
        # 缺少一个屏幕边界判断 游戏窗口拖动后可能会超出整个屏幕
        return rect.left_top + gp if gp is not None else None
