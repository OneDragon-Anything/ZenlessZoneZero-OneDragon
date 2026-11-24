import ctypes
from ctypes.wintypes import DWORD, RECT
from pathlib import Path
from threading import RLock
from typing import NamedTuple

import psutil
import pyautogui
import win32ui
from pygetwindow import Win32Window

from one_dragon.base.controller.window_error import WindowAmbiguousError
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log


def _get_window_thread_and_pid(hwnd: int) -> tuple[int, int]:
    """取窗口所属的线程 ID 和进程 ID。

    Raises:
        OSError: 窗口句柄已失效。
    """
    pid = DWORD()
    thread_id = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if thread_id == 0:
        raise ctypes.WinError()
    return thread_id, pid.value


class _Binding(NamedTuple):
    """一次绑定的窗口与进程身份快照。"""

    win: Win32Window
    hwnd: int
    process: psutil.Process
    thread_id: int


class PcGameWindow:
    """持有唯一控制窗口的 PC 游戏窗口。

    锁只保护绑定字段的读写，持锁期间不做窗口枚举、读标题等可能卡住的跨进程调用。
    窗口查找（``init_win``）在锁外进行，写入前在锁内再次确认，因此界面线程调用
    ``peek_*`` 系列接口时不会被后台线程的查找卡住。
    """

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
        win = self.peek_win()
        # 读标题是跨进程调用，放在锁外
        return win.title if win is not None else None

    def _clear_cached_window(self) -> None:
        """释放唯一绑定及其进程身份，调用方须持有绑定锁。"""
        self._win = None
        self._hWnd = None
        self._process = None
        self._thread_id = None

    def _snapshot(self) -> _Binding | None:
        """在锁内取当前绑定字段的快照，不做任何系统调用。"""
        with self._binding_lock:
            if self._win is None or self._hWnd is None or self._process is None or self._thread_id is None:
                return None
            return _Binding(self._win, self._hWnd, self._process, self._thread_id)

    @staticmethod
    def _is_identity_valid(hwnd: int, process: psutil.Process, thread_id: int) -> bool:
        """核对窗口、所属线程及进程身份，防止句柄或 PID 复用。"""
        if not ctypes.windll.user32.IsWindow(hwnd):
            return False
        try:
            current_thread_id, pid = _get_window_thread_and_pid(hwnd)
            return (current_thread_id == thread_id and pid == process.pid
                    and process.is_running())
        except (OSError, psutil.NoSuchProcess):
            log.debug('核对绑定窗口时窗口或进程已退出', exc_info=True)
            return False

    def _is_binding_valid(self) -> bool:
        """当前绑定是否仍指向原窗口和原进程。"""
        binding = self._snapshot()
        return binding is not None and self._is_identity_valid(binding.hwnd, binding.process, binding.thread_id)

    def _release_if_current(self, binding: _Binding) -> None:
        """仅当绑定仍是这份快照时释放，避免清掉其他线程刚建立的新绑定。"""
        with self._binding_lock:
            if self._hWnd == binding.hwnd and self._process is binding.process:
                self._clear_cached_window()

    def _valid_binding(self) -> _Binding | None:
        """返回仍有效的绑定；失效时释放，不查找新窗口。"""
        binding = self._snapshot()
        if binding is None:
            return None
        if self._is_identity_valid(binding.hwnd, binding.process, binding.thread_id):
            return binding
        self._release_if_current(binding)
        return None

    @staticmethod
    def _find_candidate(titles: tuple[str, ...]) -> _Binding | None:
        """按标题优先级查找唯一窗口，不读写绑定字段，也不持锁。

        Raises:
            WindowAmbiguousError: 首个匹配标题对应多个窗口。
        """
        for title in titles:
            # 枚举窗口和读取标题都可能因其他窗口无响应而长时间阻塞
            windows = [win for win in pyautogui.getWindowsWithTitle(title)
                       if win.title == title and ctypes.windll.user32.IsWindow(win._hWnd)]
            if len(windows) > 1:
                raise WindowAmbiguousError(f'找到多个标题为“{title}”的窗口，请关闭多余窗口后重试')
            if not windows:
                continue
            win = windows[0]
            try:
                thread_id, pid = _get_window_thread_and_pid(win._hWnd)
                process = psutil.Process(pid)
            except (OSError, psutil.NoSuchProcess):
                log.debug('绑定窗口时进程已退出', exc_info=True)
                return None
            return _Binding(win, win._hWnd, process, thread_id)
        return None

    def init_win(self) -> None:
        """保留有效绑定；否则按标题优先级选择唯一窗口。

        查找在锁外进行；写入前在锁内再次确认候选配置未变、且没有其他线程先绑定好有效窗口。

        Raises:
            WindowAmbiguousError: 首个匹配标题对应多个窗口。
        """
        if self._valid_binding() is not None:
            return
        titles = self._win_titles
        candidate = self._find_candidate(titles)
        if candidate is None:
            return
        if not self._is_identity_valid(candidate.hwnd, candidate.process, candidate.thread_id):
            return
        with self._binding_lock:
            if self._win_titles != titles:
                return  # 查找期间候选配置已变化，丢弃旧结果
            if self._is_binding_valid():
                return  # 其他线程已先绑定，保留已有目标
            self._win = candidate.win
            self._hWnd = candidate.hwnd
            self._process = candidate.process
            self._thread_id = candidate.thread_id

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
        """获取唯一控制窗口，失效时重新发现（可能枚举窗口，界面线程请用 peek_win）。"""
        self.init_win()
        binding = self._snapshot()
        return binding.win if binding is not None else None

    def get_hwnd(self) -> int | None:
        """获取唯一控制句柄，失效时重新发现（可能枚举窗口，界面线程请用 peek_hwnd）。"""
        self.init_win()
        binding = self._snapshot()
        return binding.hwnd if binding is not None else None

    def peek_win(self) -> Win32Window | None:
        """只读当前有效绑定的窗口，不查找新窗口，可在界面线程和定时器里调用。"""
        binding = self._valid_binding()
        return binding.win if binding is not None else None

    def peek_hwnd(self) -> int | None:
        """只读当前有效绑定的句柄，不查找新窗口，可在界面线程和定时器里调用。"""
        binding = self._valid_binding()
        return binding.hwnd if binding is not None else None

    @property
    def is_bound_valid(self) -> bool:
        """当前是否已有有效绑定，不查找新窗口。"""
        return self._valid_binding() is not None

    def peek_win_rect(self) -> Rect | None:
        """只读当前有效绑定窗口的客户区位置，不查找新窗口，也不恢复最小化窗口。"""
        hwnd = self.peek_hwnd()
        if hwnd is None:
            return None
        got_rect, client_rect = self._try_get_client_rect(hwnd)
        if not self._is_valid_client_rect(got_rect, client_rect):
            return None
        return self._client_rect_to_screen(hwnd, client_rect)

    def get_executable_path(self) -> str:
        """读取绑定窗口的进程路径，不激活窗口或初始化截图。

        Raises:
            FileNotFoundError: 没有窗口、进程退出或路径无效。
            psutil.AccessDenied: 系统拒绝读取进程信息。
            WindowAmbiguousError: 无法唯一选择控制窗口。
        """
        self.init_win()
        binding = self._snapshot()
        if binding is None:
            raise FileNotFoundError('未找到运行中的游戏窗口，请先启动游戏')
        try:
            executable = binding.process.exe()
            if not self._is_identity_valid(binding.hwnd, binding.process, binding.thread_id):
                self._release_if_current(binding)
                raise FileNotFoundError('读取期间游戏进程已退出，请重试')
        except psutil.NoSuchProcess as error:
            self._release_if_current(binding)
            raise FileNotFoundError('读取期间游戏进程已退出，请重试') from error
        path = Path(executable)
        if not executable or path.suffix.lower() != '.exe' or not path.is_file():
            raise FileNotFoundError('游戏进程的可执行文件路径无效，请手动选择')
        return str(path)

    def _reset_cached_window(self, hwnd: int | None = None) -> None:
        """释放失效绑定，后续按候选规则重新发现。

        Args:
            hwnd: 发现失效的句柄；传入时只在绑定仍是该句柄时释放。
        """
        with self._binding_lock:
            if hwnd is None or self._hWnd == hwnd:
                self._clear_cached_window()

    @staticmethod
    def _try_get_client_rect(hwnd: int) -> tuple[bool, RECT]:
        client_rect = RECT()
        got_rect = ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(client_rect)) != 0
        return got_rect, client_rect

    @staticmethod
    def _is_valid_client_rect(got_rect: bool, client_rect: RECT) -> bool:
        return got_rect and client_rect.right > 0 and client_rect.bottom > 0

    @staticmethod
    def _client_rect_to_screen(hwnd: int, client_rect: RECT) -> Rect:
        left_top_pos = ctypes.wintypes.POINT(client_rect.left, client_rect.top)
        ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(left_top_pos))
        return Rect(left_top_pos.x, left_top_pos.y, left_top_pos.x + client_rect.right, left_top_pos.y + client_rect.bottom)

    @property
    def is_win_valid(self) -> bool:
        """当前窗口是否正常；未绑定时会查找窗口，界面线程请用 is_bound_valid。"""
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
                self._reset_cached_window(win._hWnd)
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
                    self._reset_cached_window(win._hWnd)
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
            self._reset_cached_window(hwnd)
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

        return self._client_rect_to_screen(hwnd, client_rect)

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
