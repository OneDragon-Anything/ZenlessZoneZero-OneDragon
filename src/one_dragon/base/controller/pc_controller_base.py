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
        self.game_win.active()

    def set_window_title(self, new_title: str) -> None:
        """
        设置窗口标题
        :param new_title: 新的窗口标题
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

    @property
    def is_game_window_ready(self) -> bool:
        """
        游戏窗口是否已经准备好了
        :return:
        """
        return self.game_win.is_win_valid

    def click(self, pos: Point = None, press_time: float = 0, pc_alt: bool = False) -> bool:
        """
        点击位置
        :param pos: 游戏中的位置 (x,y)
        :param press_time: 大于0时长按若干秒
        :param pc_alt: 只在PC端有用 使用ALT键进行点击
        :return: 不在窗口区域时不点击 返回False
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

    def gamepad_click(self, gamepad_key: list[str] | None) -> bool:
        """后台模式下使用手柄按键替代 pc_alt 点击。

        高层 click_area / find_and_click_area 在 pc_alt=True 时调用此方法。
        仅在后台模式且 gamepad_key 不为空时执行手柄按键。

        :param gamepad_key: 手柄按键列表，如 ['xbox_0'] 或 ['xbox_6', 'xbox_0']，为 None 时不执行
        :return: True 表示已用手柄替代，False 表示未替代（应回退到普通 click）
        """
        if self.background_mode and gamepad_key:
            if len(gamepad_key) == 1:
                self.btn_controller.tap(gamepad_key[0])
            else:
                self.btn_controller.tap_combo(gamepad_key)
            return True
        return False

    # ── 后台模式 API ──────────────────────────────────

    def send_activate(self) -> bool:
        """
        发送 WM_ACTIVATE(WA_ACTIVE) 到游戏窗口。
        让游戏认为自己被激活，但不实际改变前台窗口。
        后台 PostMessage 点击前必须调用。
        :return: 是否成功
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
        """
        后台点击: WM_ACTIVATE + WM_MOUSEMOVE + PostMessage WM_LBUTTONDOWN/UP。
        适用于 UI/菜单等非锁鼠标场景。
        :param pos: 游戏中的位置 (x,y)，None 时 lParam=0
        :param press_time: 大于0时长按
        :return: 是否成功
        """
        hwnd = self.game_win.get_hwnd()
        if hwnd is None:
            log.error('游戏窗口未就绪，无法后台点击')
            return False

        # 计算客户区相对坐标
        if pos is not None:
            scaled_pos = self.game_win.get_scaled_game_pos(pos)
            if scaled_pos is None:
                log.error('点击非游戏窗口区域 (%s)', pos)
                return False
            cx, cy = int(scaled_pos.x), int(scaled_pos.y)
            lparam = win32api.MAKELONG(cx, cy)
        else:
            lparam = 0

        try:
            # 1. WM_ACTIVATE — 欺骗游戏认为窗口被激活
            win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
            time.sleep(0.01)

            # 2. WM_MOUSEMOVE — 先移动到目标位置
            win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
            time.sleep(0.01)

            # 3. WM_LBUTTONDOWN
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            if press_time > 0:
                time.sleep(press_time)
            else:
                time.sleep(0.02)

            # 4. WM_LBUTTONUP
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            return True
        except Exception:
            log.error('后台点击失败', exc_info=True)
            return False

    def enable_background_mode(self) -> None:
        """
        启用纯后台模式:
        - 鼠标点击 → PostMessage (WM_ACTIVATE + PostMessage)
        - 按键操作 → Xbox 虚拟手柄 (vgamepad)
        - pc_alt 场景 → 手柄按键替代
        需要先安装 ViGEmBus 驱动和 vgamepad 包。
        """
        self.background_mode = True
        self.enable_xbox()
        log.info('已启用后台模式: PostMessage 点击 + Xbox 手柄')

    def enable_foreground_mode(self) -> None:
        """
        启用前台模式 (默认):
        - 鼠标点击 → pyautogui
        - 按键操作 → 键盘 (pynput)
        """
        self.background_mode = False
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
        """
        向下滚动
        :param down: 负数时为相上滚动
        :param pos: 滚动位置 默认分辨率下的游戏窗口里的坐标
        :return:
        """
        if pos is None:
            pos = get_current_mouse_pos()
        win_pos = self.game_win.game2win_pos(pos)
        if win_pos is None:
            log.error('滚动位置不在游戏窗口区域 (%s)', pos)
            return
        win_scroll(down, win_pos)

    def drag_to(self, end: Point, start: Point = None, duration: float = 0.5):
        """
        按住拖拽
        :param end: 拖拽目的点
        :param start: 拖拽开始点
        :param duration: 拖拽持续时间
        :return:
        """
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

    def close_game(self):
        """
        关闭游戏
        :return:
        """
        win = self.game_win.get_win()
        if win is None:
            return
        try:
            win.close()
            log.info('关闭游戏成功')
        except Exception:
            log.error('关闭游戏失败', exc_info=True)

    def input_str(self, to_input: str, interval: float = 0.1):
        """
        输入文本 需要自己先选择好输入框
        :param to_input: 文本
        :return:
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
    """
    点击鼠标
    :param pos: 屏幕坐标
    :param press_time: 按住时间
    :param primary: 是否点击鼠标主要按键（通常是左键）
    :return:
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
    """
    向下滚动
    :param clicks: 负数时为相上滚动
    :param pos: 滚动位置 不传入时为鼠标当前位置
    :return:
    """
    if pos is not None:
        pyautogui.moveTo(pos.x, pos.y)
    d = 2000 if get_mouse_sensitivity() <= 10 else 1000
    pyautogui.scroll(-d * clicks, pos.x, pos.y)


@lru_cache
def get_mouse_sensitivity():
    """
    获取鼠标灵敏度
    :return:
    """
    user32 = ctypes.windll.user32
    speed = ctypes.c_int()
    user32.SystemParametersInfoA(0x0070, 0, ctypes.byref(speed), 0)
    return speed.value


def drag_mouse(start: Point, end: Point, duration: float = 0.5):
    """
    按住鼠标左键进行画面拖动
    :param start: 原位置
    :param end: 拖动位置
    :param duration: 拖动鼠标到目标位置，持续秒数
    :return:
    """
    pyautogui.moveTo(start.x, start.y)  # 将鼠标移动到起始位置
    pyautogui.dragTo(end.x, end.y, duration=duration)


def get_current_mouse_pos() -> Point:
    """
    获取鼠标当前坐标
    :return:
    """
    pos = pyautogui.position()
    return Point(pos.x, pos.y)
