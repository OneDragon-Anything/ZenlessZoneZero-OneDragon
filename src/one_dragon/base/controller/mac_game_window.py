import Quartz
from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log


class MacGameWindowHandle:
    """macOS 游戏窗口的进程句柄。"""

    def __init__(self, window_id: int, owner_pid: int, title: str):
        self.window_id: int = window_id
        self.owner_pid: int = owner_pid
        self.title: str = title

    @property
    def isActive(self) -> bool:
        """游戏窗口所属应用是否处于前台。"""
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
            self.owner_pid
        )
        return app is not None and app.isActive()

    def activate(self) -> bool:
        """将游戏窗口所属应用切到前台。"""
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
            self.owner_pid
        )
        if app is None:
            return False
        return bool(
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        )


class MacPcGameWindow:
    """通过 macOS 窗口列表定位 PlayCover 中的游戏窗口。"""

    GAME_TITLE_ALIASES: dict[str, set[str]] = {
        '绝区零': {'绝区零', '絕區零'},
        '絕區零': {'绝区零', '絕區零'},
    }

    def __init__(
        self,
        standard_width: int = 1920,
        standard_height: int = 1080,
    ):
        self.win_title: str | None = None
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height
        self.standard_game_rect: Rect = Rect(0, 0, standard_width, standard_height)
        self._win: MacGameWindowHandle | None = None
        self._window_id: int | None = None

    def _clear_cached_window(self) -> None:
        self._win = None
        self._window_id = None

    @staticmethod
    def _get_windows() -> list[dict]:
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        return list(windows or [])

    def init_win(self) -> None:
        """查找标题与配置相符的可见游戏窗口。"""
        if not self.win_title:
            return

        for window in self._get_windows():
            title = str(window.get(Quartz.kCGWindowName, '') or '')
            owner_name = str(window.get(Quartz.kCGWindowOwnerName, '') or '')
            expected_titles = self.GAME_TITLE_ALIASES.get(
                self.win_title, {self.win_title}
            )
            if not any(
                expected in candidate
                for expected in expected_titles
                for candidate in (title, owner_name)
            ):
                continue

            window_id = window.get(Quartz.kCGWindowNumber)
            owner_pid = window.get(Quartz.kCGWindowOwnerPID)
            if window_id is None or owner_pid is None:
                continue

            self._window_id = int(window_id)
            self._win = MacGameWindowHandle(
                self._window_id,
                int(owner_pid),
                title or owner_name,
            )
            return

        self._clear_cached_window()

    def update_win_title(self, new_title: str) -> None:
        """更新窗口标题并清除缓存。"""
        if self.win_title != new_title:
            self.win_title = new_title
            self._clear_cached_window()

    def refresh_win(self) -> None:
        self._clear_cached_window()
        self.init_win()

    def get_win(self) -> MacGameWindowHandle | None:
        if self._win is None:
            self.init_win()
        return self._win

    def get_hwnd(self) -> int | None:
        if self._window_id is None:
            self.init_win()
        return self._window_id

    @property
    def is_win_valid(self) -> bool:
        """检查缓存的游戏窗口是否仍然显示。"""
        window_id = self.get_hwnd()
        if window_id is None:
            return False
        if any(
            int(window.get(Quartz.kCGWindowNumber, -1)) == window_id
            for window in self._get_windows()
        ):
            return True
        self._clear_cached_window()
        return False

    @property
    def is_win_active(self) -> bool:
        window = self.get_win()
        return window.isActive if window is not None else False

    @property
    def win_rect(self) -> Rect | None:
        """获取游戏窗口在桌面上的位置。"""
        window_id = self.get_hwnd()
        if window_id is None:
            return None

        for window in self._get_windows():
            if int(window.get(Quartz.kCGWindowNumber, -1)) != window_id:
                continue
            bounds = window.get(Quartz.kCGWindowBounds, {})
            x = int(bounds.get('X', 0))
            y = int(bounds.get('Y', 0))
            width = int(bounds.get('Width', 0))
            height = int(bounds.get('Height', 0))
            if width <= 0 or height <= 0:
                return None
            game_height = min(
                height,
                round(width * self.standard_height / self.standard_width),
            )
            title_bar_height = height - game_height
            return Rect(
                x,
                y + title_bar_height,
                x + width,
                y + height,
            )

        self._clear_cached_window()
        return None

    @property
    def is_win_scale(self) -> bool:
        rect = self.win_rect
        return rect is not None and (
            rect.width != self.standard_width or rect.height != self.standard_height
        )

    def active(self) -> bool:
        window = self.get_win()
        if window is None:
            return False
        if window.isActive:
            return True
        if not window.activate():
            log.error('无法激活 PlayCover 游戏窗口，请检查系统辅助功能权限')
            return False
        return True

    def get_scaled_game_pos(self, game_pos: Point) -> Point | None:
        rect = self.win_rect
        if rect is None:
            return None
        xs = rect.width / self.standard_width
        ys = rect.height / self.standard_height
        scaled_pos = Point(game_pos.x * xs, game_pos.y * ys)
        return (
            scaled_pos
            if self.is_valid_game_pos(game_pos, self.standard_game_rect)
            else None
        )

    @staticmethod
    def is_valid_game_pos(s_pos: Point, rect: Rect | None = None) -> bool:
        if rect is None:
            return s_pos.x >= 0 and s_pos.y >= 0
        return 0 <= s_pos.x < rect.width and 0 <= s_pos.y < rect.height

    def game2win_pos(self, game_pos: Point) -> Point | None:
        rect = self.win_rect
        scaled_pos = self.get_scaled_game_pos(game_pos)
        if rect is None or scaled_pos is None:
            return None
        return rect.left_top + scaled_pos
