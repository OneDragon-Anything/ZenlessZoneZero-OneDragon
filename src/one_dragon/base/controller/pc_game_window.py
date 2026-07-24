import ctypes
import time
from ctypes.wintypes import RECT

import pyautogui
import win32con
import win32gui
from pygetwindow import Win32Window

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log


class PcGameWindow:

    MAX_ACTIVE_ATTEMPTS = 30

    def __init__(self,
                 standard_width: int = 1920,
                 standard_height: int = 1080):
        self.win_title: str | None = None
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height
        self.standard_game_rect: Rect = Rect(0, 0, standard_width, standard_height)

        self._win: Win32Window | None = None
        self._hWnd: int | None = None

    def _clear_cached_window(self) -> None:
        self._win = None
        self._hWnd = None

    def init_win(self) -> None:
        """
        初始化窗口
        :return:
        """
        self._clear_cached_window()
        if self.win_title is None:
            return

        windows = pyautogui.getWindowsWithTitle(self.win_title)
        for win in windows:
            if win.title == self.win_title:
                self._win = win
                self._hWnd = win._hWnd
                return

    def update_win_title(self, new_title: str) -> None:
        """
        更新窗口标题并清除缓存的窗口句柄
        :param new_title: 新的窗口标题
        """
        if self.win_title != new_title:
            self.win_title = new_title
            self._clear_cached_window()

    def refresh_win(self) -> None:
        self.init_win()

    def get_win(self) -> Win32Window | None:
        if self._win is None:
            self.init_win()
        return self._win

    def get_hwnd(self) -> int | None:
        if self._hWnd is None:
            self.init_win()
        return self._hWnd

    @staticmethod
    def _try_get_client_rect(hwnd: int) -> tuple[bool, RECT]:
        client_rect = RECT()
        got_rect = ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(client_rect)) != 0
        return got_rect, client_rect

    @staticmethod
    def _is_valid_client_rect(got_rect: bool, client_rect: RECT) -> bool:
        return got_rect and client_rect.right > 0 and client_rect.bottom > 0

    @property
    def is_win_valid(self) -> bool:
        """
        当前窗口是否正常
        :return:
        """
        win = self.get_win()
        hwnd = self._hWnd
        is_valid = win is not None and hwnd is not None and win32gui.IsWindow(hwnd)
        if not is_valid:
            self._clear_cached_window()
        return is_valid

    @property
    def is_win_active(self) -> bool:
        """
        是否当前激活的窗口
        :return:
        """
        return self.is_win_valid and win32gui.GetForegroundWindow() == self._hWnd

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

    def active(self, retry_until_active: bool = False) -> bool:
        """
        显示并激活当前窗口
        :param retry_until_active: 是否最多重试 30 次，并在多次失败后最小化其他窗口
        :return: 是否已确认游戏窗口位于前台
        """
        if not self.is_win_valid:
            return False
        if self.is_win_active:
            return True

        attempt = 0
        while self.is_win_valid:
            if retry_until_active and attempt >= 10 and attempt % 10 == 0:
                log.info('多次尝试未恢复，尝试最小化其他窗口后激活游戏窗口')
                self._minimize_other_windows()
            else:
                log.info('游戏窗口未获得焦点，尝试恢复窗口')

            self._focus_window()
            time.sleep(0.05)
            if win32gui.GetForegroundWindow() == self._hWnd:
                log.info('游戏窗口已恢复前台焦点')
                return True
            if not retry_until_active:
                log.error('切换到游戏窗口失败，Windows 未允许窗口获得前台焦点')
                return False
            attempt += 1
            if attempt >= self.MAX_ACTIVE_ATTEMPTS:
                log.error('多次尝试仍未恢复游戏窗口前台焦点')
                return False
            time.sleep(1)

        log.error('游戏窗口已失效，无法恢复前台焦点')
        return False

    def _minimize_other_windows(self) -> None:
        """通过任务栏命令最小化其他窗口。"""
        try:
            shell_hwnd = win32gui.FindWindow('Shell_TrayWnd', None)
            if shell_hwnd:
                win32gui.PostMessage(shell_hwnd, win32con.WM_COMMAND, 419, 0)
                time.sleep(0.5)
        except Exception:
            log.debug('最小化其他窗口失败', exc_info=True)

    def _focus_window(self) -> None:
        """恢复并激活窗口。"""
        hwnd = self._hWnd
        if hwnd is None or not win32gui.IsWindow(hwnd):
            self._clear_cached_window()
            return

        try:
            win32gui.PostMessage(hwnd, win32con.WM_SYSCOMMAND, win32con.SC_RESTORE, 0)

            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                log.debug('SetForegroundWindow 调用失败，继续尝试其他激活方式', exc_info=True)

            for _ in range(10):
                if not win32gui.IsIconic(hwnd):
                    break
                time.sleep(0.05)

            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            win32gui.BringWindowToTop(hwnd)
            win32gui.SetActiveWindow(hwnd)
        except Exception as error:
            if error.args and error.args[0] == 1400:
                log.warning('无效的窗口句柄，尝试重置窗口')
                self._clear_cached_window()
                return
            log.debug('请求激活游戏窗口时出现异常，继续确认前台状态', exc_info=True)

    @property
    def win_rect(self) -> Rect | None:
        """
        获取游戏窗口在桌面上面的位置
        Win32Window 里是整个window的信息 参考源码获取里面client部分的
        :return: 游戏窗口信息
        """
        win = self.get_win()
        hwnd = self._hWnd
        if win is None or hwnd is None:
            return None

        got_rect, client_rect = self._try_get_client_rect(hwnd)

        # 句柄失效时重置缓存并重试一次，避免永久复用坏句柄
        if not got_rect and ctypes.windll.user32.IsWindow(hwnd) == 0:
            log.warning('检测到失效窗口句柄，重置缓存后重试')
            self._clear_cached_window()
            win = self.get_win()
            hwnd = self._hWnd
            if win is None or hwnd is None:
                return None
            got_rect, client_rect = self._try_get_client_rect(hwnd)

        if not self._is_valid_client_rect(got_rect, client_rect) and ctypes.windll.user32.IsIconic(hwnd):
            # 最小化窗口时客户区可能为 0
            try:
                win.restore()
            except Exception:
                log.debug('win.restore 失败，尝试 ShowWindow 兜底', exc_info=True)
                ctypes.windll.user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
            got_rect, client_rect = self._try_get_client_rect(hwnd)

        if not self._is_valid_client_rect(got_rect, client_rect):
            return None

        left_top_pos = ctypes.wintypes.POINT(client_rect.left, client_rect.top)
        ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(left_top_pos))
        return Rect(left_top_pos.x, left_top_pos.y, left_top_pos.x + client_rect.right, left_top_pos.y + client_rect.bottom)

    def get_scaled_game_pos(self, game_pos: Point) -> Point | None:
        """
        获取当前分辨率下游戏窗口里的坐标
        :param game_pos: 默认分辨率下的游戏窗口里的坐标
        :return: 当前分辨率下的游戏窗口里坐标
        """
        win = self.get_win()
        rect = self.win_rect
        if win is None or rect is None:
            return None
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

    def game2win_pos(self, game_pos: Point) -> Point | None:
        """
        获取在屏幕中的坐标
        :param game_pos: 默认分辨率下的游戏窗口里的坐标
        :return: 当前分辨率下的屏幕中的坐标
        """
        rect = self.win_rect
        if rect is None:
            return None
        gp: Point | None = self.get_scaled_game_pos(game_pos)
        # 缺少一个屏幕边界判断 游戏窗口拖动后可能会超出整个屏幕
        return rect.left_top + gp if gp is not None else None
