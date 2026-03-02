import contextlib
import ctypes
import time
from functools import lru_cache

import pyautogui
import win32api
import win32con
import win32gui
from cv2.typing import MatLike
from pynput import keyboard

from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.controller.pc_button.ds4_button_controller import (
    Ds4ButtonController,
)
from one_dragon.base.controller.pc_button.keyboard_mouse_controller import (
    KeyboardMouseController,
)
from one_dragon.base.controller.pc_button.pc_button_controller import PcButtonController
from one_dragon.base.controller.pc_button.xbox_button_controller import (
    XboxButtonController,
)
from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.pc_screenshot_controller import (
    PcScreenshotController,
)
from one_dragon.base.geometry.point import Point
from one_dragon.utils.log_utils import log


class PcControllerBase(ControllerBase):

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

    def __init__(self,
                 screenshot_method: str,
                 standard_width: int = 1920,
                 standard_height: int = 1080):
        ControllerBase.__init__(self)
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height
        self.game_win: PcGameWindow = PcGameWindow(standard_width, standard_height)

        self.keyboard_controller: KeyboardMouseController = KeyboardMouseController()
        self.xbox_controller: XboxButtonController | None = None
        self.ds4_controller: Ds4ButtonController | None = None

        self.btn_controller: PcButtonController = self.keyboard_controller
        self.screenshot_controller: PcScreenshotController = PcScreenshotController(self.game_win, standard_width, standard_height)
        self.screenshot_method: str = screenshot_method
        self.background_mode: bool = False
        self.gamepad_action_keys: dict[str, str] = {}
        self._game_input_mode: str = 'keyboard_mouse'  # 游戏当前识别的输入设备

    def init_game_win(self) -> bool:
        """
        初始化游戏窗口相关内容
        Returns:
            是否初始化成功
        """
        self.game_win.init_win()
        if self.is_game_window_ready:
            self.screenshot_controller.init_screenshot(self.screenshot_method)
            return True
        else:
            return False

    def init_before_context_run(self) -> bool:
        pyautogui.FAILSAFE = False  # 禁用 Fail-Safe,防止鼠标接近屏幕的边缘或角落时报错
        self.init_game_win()
        if not self.background_mode:
            self.game_win.active()
        return True

    def cleanup_after_app_shutdown(self) -> None:
        """
        清理资源
        """
        self.screenshot_controller.cleanup()

    def active_window(self) -> None:
        """
        前置窗口
        """
        self.game_win.init_win()
        if not self.background_mode:
            self.game_win.active()

    def set_window_title(self, new_title: str) -> None:
        """设置窗口标题。

        Args:
            new_title: 新的窗口标题
        """
        self.game_win.update_win_title(new_title)

    def enable_xbox(self):
        if pc_button_utils.is_vgamepad_installed():
            if self.xbox_controller is None:
                self.xbox_controller = XboxButtonController()
            self.btn_controller = self.xbox_controller
            self.btn_controller.reset()

    def enable_ds4(self):
        if pc_button_utils.is_vgamepad_installed():
            if self.ds4_controller is None:
                self.ds4_controller = Ds4ButtonController()
            self.btn_controller = self.ds4_controller
            self.btn_controller.reset()

    def enable_keyboard(self):
        self.btn_controller = self.keyboard_controller

    def btn_tap(self, key: str) -> None:
        """按键（tap）。后台模式下先发 WM_ACTIVATE 再确保手柄输入模式。"""
        if self.background_mode:
            self.send_activate()
            self._ensure_gamepad_mode()
        self.btn_controller.tap(key)

    def btn_press(self, key: str, press_time: float | None = None) -> None:
        """按住键。后台模式下先发 WM_ACTIVATE 再确保手柄输入模式。"""
        if self.background_mode:
            self.send_activate()
            self._ensure_gamepad_mode()
        self.btn_controller.press(key, press_time)

    def btn_release(self, key: str) -> None:
        """释放键。"""
        self.btn_controller.release(key)

    @property
    def is_game_window_ready(self) -> bool:
        """游戏窗口是否已经准备好了。"""
        return self.game_win.is_win_valid

    def click(self, pos: Point = None, press_time: float = 0, pc_alt: bool = False) -> bool:
        """点击位置。

        Args:
            pos: 游戏中的位置 (x,y)
            press_time: 大于0时长按若干秒
            pc_alt: 只在PC端有用 使用ALT键进行点击

        Returns:
            不在窗口区域时不点击 返回False
        """
        if self.background_mode:
            return self.background_click(pos, press_time)

        # 默认 pyautogui 前台点击
        click_pos: Point
        if pos is not None:
            click_pos: Point = self.game_win.game2win_pos(pos)
            if click_pos is None:
                log.error('点击非游戏窗口区域 (%s)', pos)
                return False
        else:
            click_pos = get_current_mouse_pos()

        if pc_alt:
            self.keyboard_controller.keyboard.press(keyboard.Key.alt)
            time.sleep(0.2)
        win_click(click_pos, press_time=press_time)
        if pc_alt:
            self.keyboard_controller.keyboard.release(keyboard.Key.alt)
        return True

    def gamepad_click(self, gamepad_key: str | None) -> bool:
        """后台模式下使用手柄按键替代 pc_alt 点击。

        高层 click_area / find_and_click_area 在 pc_alt=True 时调用此方法。
        仅在后台模式且 gamepad_key 不为空时执行手柄按键。
        gamepad_key 是 GamepadActionEnum 的动作名 (如 'compendium')，
        通过 self.gamepad_action_keys 解析为实际按键组合 (如 'xbox_lb+xbox_a')。

        Args:
            gamepad_key: GamepadActionEnum 的存储值（动作名），由控制器解析为实际按键

        Returns:
            True 表示已用手柄替代，False 表示未替代
        """
        if not self.background_mode or not gamepad_key:
            return False

        raw_keys = self.gamepad_action_keys.get(gamepad_key, '')
        if not raw_keys:
            log.warning('后台模式: 未找到动作 %s 的手柄键映射', gamepad_key)
            return False

        self._ensure_gamepad_mode()
        self.send_activate()

        keys = raw_keys.split('+')
        if len(keys) == 1:
            self.btn_controller.tap(keys[0])
        else:
            self.btn_controller.tap_combo(keys)
        return True

    # ── 后台模式 API ──────────────────────────────────

    def _ensure_mouse_mode(self) -> None:
        """确保游戏处于键鼠输入模式。

        游戏使用 Raw Input 检测设备类型，只有窗口在前台时才处理鼠标输入。
        因此需要极短暂地将游戏窗口切到前台、发送鼠标移动、再切回。
        """
        if self._game_input_mode == 'keyboard_mouse':
            return

        hwnd = self.game_win.get_hwnd()
        if hwnd is None:
            return

        user32 = ctypes.windll.user32
        prev_hwnd = win32gui.GetForegroundWindow()

        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            log.warning('切换前台失败，无法切回键鼠模式')
            return
        time.sleep(0.05)

        # mouse_event 鼠标移动，触发 Raw Input 让游戏切回键鼠
        user32.mouse_event(self.MOUSEEVENTF_MOVE, 2, 0, 0, 0)
        time.sleep(0.05)

        # 切回原来的前台窗口
        if prev_hwnd and prev_hwnd != hwnd:
            with contextlib.suppress(Exception):
                win32gui.SetForegroundWindow(prev_hwnd)

        self._game_input_mode = 'keyboard_mouse'

    def _ensure_gamepad_mode(self) -> None:
        """确保游戏处于手柄输入模式。若当前为键鼠模式，先发一次手柄按键让游戏切换。"""
        if self._game_input_mode == 'gamepad':
            return
        self.btn_controller.tap(self._get_switch_gamepad_key())
        self._game_input_mode = 'gamepad'
        time.sleep(0.05)

    def _get_switch_gamepad_key(self) -> str:
        """获取用于切换到手柄模式的按键（使用右摇杆上推，最不易产生副作用）。"""
        if isinstance(self.btn_controller, Ds4ButtonController):
            return 'ds4_rs_up'
        return 'xbox_rs_up'

    def send_activate(self) -> bool:
        """发送 WM_ACTIVATE(WA_ACTIVE) 到游戏窗口。

        让游戏认为自己被激活，但不实际改变前台窗口。
        后台 PostMessage 点击前必须调用。

        Returns:
            是否成功
        """
        hwnd = self.game_win.get_hwnd()
        if hwnd is None:
            log.error('游戏窗口未就绪，无法发送 WM_ACTIVATE')
            return False
        try:
            win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
            time.sleep(0.01)
            return True
        except Exception:
            log.error('发送 WM_ACTIVATE 失败', exc_info=True)
            return False

    def background_click(self, pos: Point | None, press_time: float = 0) -> bool:
        """后台点击：物理移动鼠标到目标位置 + PostMessage WM_LBUTTONDOWN/UP。

        游戏不接受 lparam 中的坐标，需要用 SetCursorPos 把鼠标移过去。
        自动切换游戏到键鼠模式。

        Args:
            pos: 游戏中的位置 (x,y)，None 时不移动鼠标
            press_time: 大于0时长按

        Returns:
            是否成功
        """
        self._ensure_mouse_mode()

        hwnd = self.game_win.get_hwnd()
        if hwnd is None:
            log.error('游戏窗口未就绪，无法后台点击')
            return False

        if pos is not None:
            scaled_pos = self.game_win.get_scaled_game_pos(pos)
            if scaled_pos is None:
                log.error('点击非游戏窗口区域 (%s)', pos)
                return False
            cx, cy = int(scaled_pos.x), int(scaled_pos.y)
            # 客户端坐标 → 屏幕坐标，然后物理移动鼠标
            screen_x, screen_y = win32gui.ClientToScreen(hwnd, (cx, cy))
            win32api.SetCursorPos((screen_x, screen_y))
            time.sleep(0.01)

        return self._raw_background_click(press_time)

    def _raw_background_click(self, press_time: float = 0) -> bool:
        """底层后台点击，不做模式切换和鼠标移动。仅发 PostMessage 点击。"""
        hwnd = self.game_win.get_hwnd()
        if hwnd is None:
            log.error('游戏窗口未就绪，无法后台点击')
            return False

        try:
            win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
            time.sleep(0.01)

            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, 0)
            if press_time > 0:
                time.sleep(press_time)
            else:
                time.sleep(0.02)

            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, 0)
            return True
        except Exception:
            log.error('后台点击失败', exc_info=True)
            return False

    def enable_background_mode(self, gamepad_type: str = 'xbox') -> None:
        """启用纯后台模式。

        - 鼠标点击 → PostMessage (WM_ACTIVATE + PostMessage)
        - 按键操作 → 虚拟手柄 (vgamepad)
        - pc_alt 场景 → 手柄按键替代
        需要先安装 ViGEmBus 驱动和 vgamepad 包。

        Args:
            gamepad_type: 'xbox' 或 'ds4'
        """
        self.background_mode = True
        self._game_input_mode = 'gamepad'  # 后台模式默认游戏处于手柄输入
        if gamepad_type == 'ds4':
            self.enable_ds4()
            log.info('已启用后台模式: PostMessage 点击 + DS4 手柄')
        else:
            self.enable_xbox()
            log.info('已启用后台模式: PostMessage 点击 + Xbox 手柄')

    def enable_foreground_mode(self) -> None:
        """
        启用前台模式 (默认):
        - 鼠标点击 → pyautogui
        - 按键操作 → 键盘 (pynput)
        """
        self.background_mode = False
        self._game_input_mode = 'keyboard_mouse'
        self.enable_keyboard()
        log.info('已启用前台模式: pyautogui 点击 + 键盘')

    def get_screenshot(self, independent: bool = False) -> MatLike | None:
        if self.is_game_window_ready:
            # 确保截图器已初始化
            if not independent and self.screenshot_controller.active_strategy_name is None:
                self.screenshot_controller.init_screenshot(self.screenshot_method)
            return self.screenshot_controller.get_screenshot(independent)
        else:
            raise RuntimeError('游戏窗口未就绪')

    def scroll(self, down: int, pos: Point = None):
        """向下滚动。

        Args:
            down: 负数时为向上滚动
            pos: 滚动位置 默认分辨率下的游戏窗口里的坐标
        """
        if pos is None:
            pos = get_current_mouse_pos()
        win_pos = self.game_win.game2win_pos(pos)
        if win_pos is None:
            log.error('滚动位置不在游戏窗口区域 (%s)', pos)
            return
        win_scroll(down, win_pos)

    def drag_to(self, end: Point, start: Point = None, duration: float = 0.5):
        """按住拖拽。

        Args:
            end: 拖拽目的点
            start: 拖拽开始点
            duration: 拖拽持续时间
        """
        if self.background_mode:
            self.background_drag(start, end, duration)
            return

        from_pos: Point
        if start is None:
            from_pos = get_current_mouse_pos()
        else:
            from_pos = self.game_win.game2win_pos(start)
            if from_pos is None:
                log.error('拖拽起点不在游戏窗口区域 (%s)', start)
                return

        to_pos = self.game_win.game2win_pos(end)
        if to_pos is None:
            log.error('拖拽终点不在游戏窗口区域 (%s)', end)
            return
        drag_mouse(from_pos, to_pos, duration=duration)

    def background_drag(self, start: Point | None, end: Point, duration: float = 0.5) -> bool:
        """后台拖拽：SetCursorPos 移动鼠标 + PostMessage 按住拖动。

        使用 SetCursorPos 物理移动鼠标，分步插值模拟拖拽轨迹。

        Args:
            start: 拖拽起点（游戏坐标），None 时使用当前鼠标位置
            end: 拖拽终点（游戏坐标）
            duration: 拖拽持续时间

        Returns:
            是否成功
        """
        self._ensure_mouse_mode()

        hwnd = self.game_win.get_hwnd()
        if hwnd is None:
            log.error('游戏窗口未就绪，无法后台拖拽')
            return False

        # 转换起点坐标
        if start is not None:
            scaled_start = self.game_win.get_scaled_game_pos(start)
            if scaled_start is None:
                log.error('拖拽起点不在游戏窗口区域 (%s)', start)
                return False
            sx, sy = int(scaled_start.x), int(scaled_start.y)
        else:
            # 使用窗口中心作为默认起点
            rect = win32gui.GetClientRect(hwnd)
            sx, sy = rect[2] // 2, rect[3] // 2

        # 转换终点坐标
        scaled_end = self.game_win.get_scaled_game_pos(end)
        if scaled_end is None:
            log.error('拖拽终点不在游戏窗口区域 (%s)', end)
            return False
        ex, ey = int(scaled_end.x), int(scaled_end.y)

        try:
            win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
            time.sleep(0.01)

            # 移动到起点并按下
            screen_sx, screen_sy = win32gui.ClientToScreen(hwnd, (sx, sy))
            win32api.SetCursorPos((screen_sx, screen_sy))
            time.sleep(0.01)
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, 0)
            time.sleep(0.02)

            # 分步移动到终点
            steps = max(int(duration / 0.02), 5)
            for i in range(1, steps + 1):
                t = i / steps
                cx = int(sx + (ex - sx) * t)
                cy = int(sy + (ey - sy) * t)
                screen_cx, screen_cy = win32gui.ClientToScreen(hwnd, (cx, cy))
                win32api.SetCursorPos((screen_cx, screen_cy))
                time.sleep(duration / steps)

            # 松开
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, 0)
            return True
        except Exception:
            log.error('后台拖拽失败', exc_info=True)
            return False

    def close_game(self):
        """关闭游戏。"""
        win = self.game_win.get_win()
        if win is None:
            return
        try:
            win.close()
            log.info('关闭游戏成功')
        except Exception:
            log.error('关闭游戏失败', exc_info=True)

    def input_str(self, to_input: str, interval: float = 0.1):
        """输入文本 需要自己先选择好输入框。

        Args:
            to_input: 文本
        """
        self.keyboard_controller.keyboard.type(to_input)

    def mouse_move(self, game_pos: Point):
        """
        鼠标移动到指定的位置
        """
        win_pos = self.game_win.game2win_pos(game_pos)
        if win_pos is not None:
            pyautogui.moveTo(win_pos.x, win_pos.y)

    @property
    def center_point(self) -> Point:
        return Point(self.standard_width // 2, self.standard_height // 2)



def win_click(pos: Point = None, press_time: float = 0, primary: bool = True):
    """点击鼠标。

    Args:
        pos: 屏幕坐标
        press_time: 按住时间
        primary: 是否点击鼠标主要按键（通常是左键）
    """
    btn = pyautogui.PRIMARY if primary else pyautogui.SECONDARY
    if pos is None:
        pos = get_current_mouse_pos()
    if press_time > 0:
        pyautogui.moveTo(pos.x, pos.y)
        pyautogui.mouseDown(button=btn)
        time.sleep(press_time)
        pyautogui.mouseUp(button=btn)
    else:
        pyautogui.click(pos.x, pos.y, button=btn)


def win_scroll(clicks: int, pos: Point = None):
    """向下滚动。

    Args:
        clicks: 负数时为向上滚动
        pos: 滚动位置 不传入时为鼠标当前位置
    """
    if pos is not None:
        pyautogui.moveTo(pos.x, pos.y)
    d = 2000 if get_mouse_sensitivity() <= 10 else 1000
    pyautogui.scroll(-d * clicks, pos.x, pos.y)


@lru_cache
def get_mouse_sensitivity():
    """获取鼠标灵敏度。"""
    user32 = ctypes.windll.user32
    speed = ctypes.c_int()
    user32.SystemParametersInfoA(0x0070, 0, ctypes.byref(speed), 0)
    return speed.value


def drag_mouse(start: Point, end: Point, duration: float = 0.5):
    """按住鼠标左键进行画面拖动。

    Args:
        start: 原位置
        end: 拖动位置
        duration: 拖动鼠标到目标位置，持续秒数
    """
    pyautogui.moveTo(start.x, start.y)  # 将鼠标移动到起始位置
    pyautogui.dragTo(end.x, end.y, duration=duration)


def get_current_mouse_pos() -> Point:
    """获取鼠标当前坐标。"""
    pos = pyautogui.position()
    return Point(pos.x, pos.y)
