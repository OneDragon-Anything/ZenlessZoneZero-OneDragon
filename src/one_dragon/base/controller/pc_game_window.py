import ctypes
from ctypes.wintypes import RECT
from pathlib import Path
from threading import RLock

import psutil
import pyautogui
import pywintypes
import win32process
import win32ui
from pygetwindow import Win32Window

from one_dragon.base.controller.window_error import WindowAmbiguousError
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log


class PcGameWindow:

    def __init__(self,
                 standard_width: int = 1920,
                 standard_height: int = 1080) -> None:
        """创建只持有一个控制目标的 PC 窗口对象。"""
        self._win_titles: tuple[str, ...] = ()
        self._binding_lock: RLock = RLock()
        self._process: psutil.Process | None = None
        self._thread_id: int | None = None
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height
        self.standard_game_rect: Rect = Rect(0, 0, standard_width, standard_height)

        self._win: Win32Window | None = None
        self._hWnd: int | None = None

    @property
    def win_titles(self) -> tuple[str, ...]:
        """按首次选择优先级排列的候选标题，不允许外部原地修改。"""
        return self._win_titles

    @property
    def win_title(self) -> str | None:
        """首选的预期标题，不代表实际绑定窗口或窗口是否存在。"""
        return self._win_titles[0] if self._win_titles else None

    @property
    def bound_win_title(self) -> str | None:
        """当前有效绑定的实际标题；不触发新窗口选择。"""
        with self._binding_lock:
            if not self._is_binding_valid():
                self._clear_cached_window()
                return None
            return self._win.title

    def _clear_cached_window(self) -> None:
        """释放唯一绑定及其进程身份。"""
        self._win = None
        self._hWnd = None
        self._process = None
        self._thread_id = None

    def _is_binding_valid(self) -> bool:
        """核对窗口、所属线程及进程身份，防止句柄或 PID 复用。"""
        if self._hWnd is None or self._process is None:
            return False
        if not ctypes.windll.user32.IsWindow(self._hWnd):
            return False
        try:
            thread_id, pid = win32process.GetWindowThreadProcessId(self._hWnd)
            return (thread_id == self._thread_id and pid == self._process.pid
                    and self._process.is_running())
        except (pywintypes.error, psutil.NoSuchProcess):
            log.debug('核对绑定窗口时窗口或进程已退出', exc_info=True)
            return False

    def init_win(self) -> None:
        """保留有效绑定；否则按标题优先级选择唯一窗口。

        Raises:
            WindowAmbiguousError: 首个匹配标题对应多个窗口。
        """
        with self._binding_lock:
            if self._is_binding_valid():
                return
            self._clear_cached_window()
            for title in self._win_titles:
                windows = [win for win in pyautogui.getWindowsWithTitle(title)
                           if win.title == title and ctypes.windll.user32.IsWindow(win._hWnd)]
                if len(windows) > 1:
                    raise WindowAmbiguousError(f'找到多个标题为“{title}”的窗口，请关闭多余窗口后重试')
                if not windows:
                    continue
                win = windows[0]
                try:
                    thread_id, pid = win32process.GetWindowThreadProcessId(win._hWnd)
                    process = psutil.Process(pid)
                except (pywintypes.error, psutil.NoSuchProcess):
                    log.debug('绑定窗口时进程已退出', exc_info=True)
                    return
                self._win = win
                self._hWnd = win._hWnd
                self._process = process
                self._thread_id = thread_id
                if not self._is_binding_valid():
                    self._clear_cached_window()
                return

    def update_win_titles(self, titles: list[str]) -> None:
        """设置有序精确标题候选，仅配置实际改变时释放绑定。"""
        if not titles or any(not title.strip() for title in titles):
            raise ValueError('候选窗口标题不能为空')
        normalized = tuple(dict.fromkeys(titles))
        with self._binding_lock:
            if normalized != self._win_titles:
                self._win_titles = normalized
                self._clear_cached_window()

    def update_win_title(self, new_title: str) -> None:
        """设置唯一候选标题，保持单标题精确匹配。"""
        self.update_win_titles([new_title])

    def refresh_win(self) -> None:
        """验证并刷新窗口；有效绑定不会被其他候选窗口抢占。"""
        self.init_win()

    def get_win(self) -> Win32Window | None:
        """获取唯一控制窗口，失效时重新发现。"""
        with self._binding_lock:
            self.init_win()
            return self._win

    def get_hwnd(self) -> int | None:
        """获取唯一控制句柄，失效时重新发现。"""
        with self._binding_lock:
            self.init_win()
            return self._hWnd

    def get_executable_path(self) -> str:
        """读取绑定窗口的进程路径，不激活窗口或初始化截图。

        Raises:
            FileNotFoundError: 没有窗口、进程退出或路径无效。
            psutil.AccessDenied: 系统拒绝读取进程信息。
            WindowAmbiguousError: 无法唯一选择控制窗口。
        """
        with self._binding_lock:
            self.init_win()
            if self._process is None:
                raise FileNotFoundError('未找到运行中的游戏窗口，请先启动游戏')
            process = self._process
            try:
                executable = process.exe()
                if not self._is_binding_valid():
                    self._clear_cached_window()
                    raise FileNotFoundError('读取期间游戏进程已退出，请重试')
            except psutil.NoSuchProcess as error:
                self._clear_cached_window()
                raise FileNotFoundError('读取期间游戏进程已退出，请重试') from error
            path = Path(executable)
            if not executable or path.suffix.lower() != '.exe' or not path.is_file():
                raise FileNotFoundError('游戏进程的可执行文件路径无效，请手动选择')
            return str(path)

    def _reset_cached_window(self) -> None:
        """释放失效绑定，后续按候选规则重新发现。"""
        with self._binding_lock:
            self._clear_cached_window()

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
        with self._binding_lock:
            self.init_win()
            return self._is_binding_valid()

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
            win.restore()
            win.activate()
            return True
        except Exception as error:
            if getattr(error, 'args', None) and '1400' in str(error.args[0]):
                log.warning('无效的窗口句柄，尝试重置窗口')
                self._reset_cached_window()
                return False
            if isinstance(error, win32ui.error):
                log.error('激活窗口失败', exc_info=True)
                return False

            try:
                # 直接 activate 偶发失败，最小化再恢复可提高成功率
                win.minimize()
                win.restore()
                win.activate()
                return True
            except Exception as fallback_error:
                if getattr(fallback_error, 'args', None) and '1400' in str(fallback_error.args[0]):
                    log.warning('无效的窗口句柄，尝试重置窗口')
                    self._reset_cached_window()
                    return False
                log.error('切换到游戏窗口失败', exc_info=True)
                return False

    @property
    def win_rect(self) -> Rect | None:
        """
        获取游戏窗口在桌面上面的位置
        Win32Window 里是整个window的信息 参考源码获取里面client部分的
        :return: 游戏窗口信息
        """
        win = self.get_win()
        hwnd = win._hWnd if win is not None else None
        if win is None or hwnd is None:
            return None

        got_rect, client_rect = self._try_get_client_rect(hwnd)

        # 句柄失效时重置缓存并重试一次，避免永久复用坏句柄
        if not got_rect and ctypes.windll.user32.IsWindow(hwnd) == 0:
            log.warning('检测到失效窗口句柄，重置缓存后重试')
            self._reset_cached_window()
            win = self.get_win()
            hwnd = win._hWnd if win is not None else None
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
