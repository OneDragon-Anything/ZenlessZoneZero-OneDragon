from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import pyautogui
from cv2.typing import MatLike
from pynput import keyboard

from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.controller.macos_vhid import MacVirtualHIDMouse
from one_dragon.base.controller.pc_button import pc_button_utils
from one_dragon.base.controller.pc_button.keyboard_mouse_controller import (
    KeyboardMouseController,
)
from one_dragon.base.controller.pc_button.pc_button_controller import PcButtonController
from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.pc_screenshot_controller import (
    PcScreenshotController,
)
from one_dragon.base.geometry.point import Point
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from one_dragon.base.controller.drag_timing import DragTiming


class PcControllerBase(ControllerBase):

    SLEEP_BEFORE_DRAG_END: float = 0.2
    DRAG_MIN_DURATION: float = 0.1
    MAC_MOUSE_MOVE_SETTLE: float = 0.1

    def __init__(self,
                 screenshot_method: str,
                 standard_width: int = 1920,
                 standard_height: int = 1080,
                 keyboard_mouse_controller: KeyboardMouseController | None = None):
        ControllerBase.__init__(self)
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height
        self.game_win: PcGameWindow = PcGameWindow(standard_width, standard_height)

        self.keyboard_controller: KeyboardMouseController = (
            keyboard_mouse_controller
            if keyboard_mouse_controller is not None
            else KeyboardMouseController()
        )
        self.btn_controller: PcButtonController = self.keyboard_controller
        self.screenshot_controller: PcScreenshotController = PcScreenshotController(self.game_win, standard_width, standard_height)
        self.screenshot_method: str = screenshot_method
        self._mac_virtual_hid_mouse: MacVirtualHIDMouse | None = None

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
        pyautogui.PAUSE = 0.001  # pyautogui的操作会有延迟, 一些需要低延迟的操作中会取消这个延迟然后恢复延迟, 以免影响其他功能
        pyautogui.FAILSAFE = False  # 禁用 Fail-Safe,防止鼠标接近屏幕的边缘或角落时报错
        if sys.platform == 'darwin':
            try:
                if self._mac_virtual_hid_mouse is None:
                    self._mac_virtual_hid_mouse = MacVirtualHIDMouse()
            except (OSError, RuntimeError, TimeoutError) as e:
                log.error('初始化 macOS 虚拟鼠标失败: %s', e)
                return False
        self.init_game_win()
        self.game_win.active()
        return True

    def cleanup_after_app_shutdown(self) -> None:
        """
        清理资源
        """
        self.btn_controller.reset()
        if self._mac_virtual_hid_mouse is not None:
            self._mac_virtual_hid_mouse.close()
            self._mac_virtual_hid_mouse = None
        self.screenshot_controller.cleanup()

    def active_window(self) -> None:
        """
        前置窗口
        """
        self.game_win.init_win()
        self.game_win.active()

    def set_window_title(self, new_title: str) -> None:
        """设置窗口标题。

        Args:
            new_title: 新的窗口标题
        """
        self.game_win.update_win_title(new_title)

    def enable_keyboard(self):
        self.btn_controller = self.keyboard_controller

    def btn_tap(self, key: str) -> None:
        """点按键盘按键。"""
        if sys.platform == 'darwin' and pc_button_utils.is_mouse_button(key):
            self._get_mac_virtual_hid_mouse().click(
                button=pc_button_utils.get_mouse_button(key).name
            )
            return
        self.btn_controller.tap(key)

    def btn_press(self, key: str, press_time: float | None = None) -> None:
        """按住键盘按键。"""
        if sys.platform == 'darwin' and pc_button_utils.is_mouse_button(key):
            mouse_button = pc_button_utils.get_mouse_button(key).name
            mouse = self._get_mac_virtual_hid_mouse()
            mouse.press(mouse_button)
            if press_time is not None:
                try:
                    time.sleep(press_time)
                finally:
                    mouse.release(mouse_button)
            return
        self.btn_controller.press(key, press_time)

    def btn_release(self, key: str) -> None:
        """释放键。"""
        if sys.platform == 'darwin' and pc_button_utils.is_mouse_button(key):
            self._get_mac_virtual_hid_mouse().release(
                pc_button_utils.get_mouse_button(key).name
            )
            return
        self.btn_controller.release(key)

    def _get_mac_virtual_hid_mouse(self) -> MacVirtualHIDMouse:
        if self._mac_virtual_hid_mouse is None:
            raise RuntimeError(
                'macOS 虚拟鼠标未初始化；请先运行启动脚本并确认 Karabiner 虚拟 HID 服务正常'
            )
        return self._mac_virtual_hid_mouse

    @property
    def is_game_window_ready(self) -> bool:
        """游戏窗口是否已经准备好了。"""
        return self.game_win.is_win_valid

    def close_game(self) -> None:
        win = self.game_win.get_win()
        if win is None:
            return
        if sys.platform == 'darwin':
            log.error('macOS 暂不支持从一条龙关闭 PlayCover 中的游戏')
            return
        try:
            win.close()
            log.info('关闭游戏成功')
        except Exception:
            log.error('关闭游戏失败', exc_info=True)

    def get_screenshot(self, independent: bool = False) -> MatLike | None:
        if self.is_game_window_ready:
            # 确保截图器已初始化
            if not independent and self.screenshot_controller.active_strategy_name is None:
                self.screenshot_controller.init_screenshot(self.screenshot_method)
            return self.screenshot_controller.get_screenshot(independent)
        else:
            raise RuntimeError('游戏窗口未就绪')

    def enable_foreground_mode(self) -> None:
        """启用前台键鼠模式。"""
        self.enable_keyboard()
        log.info('已启用前台键鼠模式')

    def click(self, pos: Point = None, press_time: float = 0.1, pc_alt: bool = False) -> bool:
        """点击位置。

        Args:
            pos: 游戏中的位置 (x,y)
            press_time: 大于0时长按若干秒
            pc_alt: 只在PC端有用 使用ALT键进行点击
        Returns:
            不在窗口区域时不点击 返回False
        """
        return self._foreground_click(pos, press_time, pc_alt)

    def _foreground_click(self, pos: Point | None, press_time: float = 0.1, pc_alt: bool = False) -> bool:
        """前台点击，可选按住 ALT 解锁光标。

        Args:
            pos: 游戏中的位置 (x,y)，None 时使用当前鼠标位置
            press_time: 大于0时长按
            pc_alt: 是否先按住 ALT 再点击

        Returns:
            是否成功
        """
        click_pos: Point
        if pos is not None:
            click_pos: Point = self.game_win.game2win_pos(pos)
            if click_pos is None:
                log.error('点击非游戏窗口区域 (%s)', pos)
                return False
        else:
            click_pos = get_current_mouse_pos()

        alt_pressed = False
        try:
            if pc_alt:
                self.keyboard_controller.keyboard.press(keyboard.Key.alt)
                alt_pressed = True
                time.sleep(0.2)
            if sys.platform == 'darwin':
                if self._mac_virtual_hid_mouse is None:
                    log.error('macOS 虚拟鼠标未初始化；请先运行启动脚本并确认 Karabiner 虚拟 HID 服务正常')
                    return False
                pyautogui.moveTo(click_pos.x, click_pos.y)
                actual_pos = pyautogui.position()
                log.info(
                    'macOS 鼠标定位: 游戏坐标=%s, 目标桌面坐标=(%s, %s), 实际桌面坐标=(%s, %s)',
                    pos,
                    click_pos.x,
                    click_pos.y,
                    actual_pos.x,
                    actual_pos.y,
                )
                time.sleep(self.MAC_MOUSE_MOVE_SETTLE)
                self._mac_virtual_hid_mouse.click(press_time=press_time)
            else:
                win_click(click_pos, press_time=press_time)
        except (OSError, RuntimeError, TimeoutError) as e:
            log.error('鼠标点击失败: %s', e)
            return False
        finally:
            if alt_pressed:
                self.keyboard_controller.keyboard.release(keyboard.Key.alt)
        return True

    def drag_to(
        self, end: Point, start: Point | None = None, duration: float = 0.5,
        *, timing: DragTiming | None = None,
    ) -> None:
        """按住拖拽。

        Args:
            end: 拖拽目的点。
            start: 拖拽开始点。
            duration: 未指定 timing 时的原有时长预算。
            timing: 显式指定三段时序；提供时忽略 duration，None 保留原行为。
        """
        if start is None:
            start = get_current_mouse_pos()

        return self._foreground_drag(start, end, duration, timing=timing)

    def _foreground_drag(
        self, start: Point, end: Point, duration: float = 0.5,
        *, timing: DragTiming | None = None,
    ) -> None:
        """前台拖拽：通过 pyautogui 按住拖动。

        Args:
            start: 拖拽起点（游戏坐标）
            end: 拖拽终点（游戏坐标）
            duration: 未指定 timing 时的原有时长预算。
            timing: 显式三段时序，None 保留原行为。
        """
        from_pos = self.game_win.game2win_pos(start)
        if from_pos is None:
            log.error('拖拽起点不在游戏窗口区域 (%s)', start)
            return

        to_pos = self.game_win.game2win_pos(end)
        if to_pos is None:
            log.error('拖拽终点不在游戏窗口区域 (%s)', end)
            return
        if sys.platform == 'darwin':
            mouse = self._get_mac_virtual_hid_mouse()
            drag_mouse(
                from_pos,
                to_pos,
                duration=duration,
                timing=timing,
                button_down=lambda: mouse.press('left'),
                button_up=lambda: mouse.release('left'),
            )
        else:
            drag_mouse(from_pos, to_pos, duration=duration, timing=timing)

    def scroll(self, down: int, pos: Point | None = None) -> None:
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

    def input_str(self, to_input: str, interval: float = 0.1) -> None:
        """输入文本 需要自己先选择好输入框。

        Args:
            to_input: 文本
        """
        self.keyboard_controller.keyboard.type(to_input)

    def mouse_move(self, game_pos: Point) -> None:
        """
        鼠标移动到指定的位置
        """
        win_pos = self.game_win.game2win_pos(game_pos)
        if win_pos is not None:
            pyautogui.moveTo(win_pos.x, win_pos.y)
            time.sleep(0.1)  # 原本 pyautogui 的操作会有0.1s延迟, 现在去掉了, 故在这里加上延迟

    @property
    def center_point(self) -> Point:
        return Point(self.standard_width // 2, self.standard_height // 2)


def win_click(pos: Point = None, press_time: float = 0.1, primary: bool = True):
    """点击鼠标。

    Args:
        pos: 屏幕坐标
        press_time: 按住时间
        primary: 是否点击鼠标主要按键（通常是左键）
    """
    btn = pyautogui.PRIMARY if primary else pyautogui.SECONDARY
    if pos is None:
        pos = get_current_mouse_pos()

    pyautogui.moveTo(pos.x, pos.y)
    pyautogui.mouseDown(button=btn)
    time.sleep(max(0.001, press_time))
    pyautogui.mouseUp(button=btn)


def win_scroll(clicks: int, pos: Point | None = None) -> None:
    """向下滚动。

    Args:
        clicks: 负数时为向上滚动
        pos: 滚动位置 不传入时为鼠标当前位置
    """
    if pos is None:
        pos = get_current_mouse_pos()
    pyautogui.moveTo(pos.x, pos.y)
    pyautogui.scroll(-120 * clicks, pos.x, pos.y)


def drag_mouse(
    start: Point, end: Point, duration: float = 0.5,
    *, timing: DragTiming | None = None,
    button_down: Callable[[], None] | None = None,
    button_up: Callable[[], None] | None = None,
) -> None:
    """按住鼠标左键进行画面拖动 (消除拖动后的惯性)。

    Args:
        start: 原位置
        end: 拖动位置
        duration: 未指定 timing 时的原有时长预算。
        timing: 显式三段时序，None 保留原行为。
    """

    # 移动到起点并按下
    pyautogui.moveTo(start.x, start.y)
    (button_down or pyautogui.mouseDown)()
    try:
        if timing is not None and timing.press_wait > 0:
            time.sleep(timing.press_wait)

        # 默认前台不增加按下等待，保留原有计算方式。
        release_wait = PcControllerBase.SLEEP_BEFORE_DRAG_END if timing is None else timing.release_wait
        move_duration = duration - release_wait if timing is None else timing.move_duration
        duration_drag = max(move_duration, PcControllerBase.DRAG_MIN_DURATION)
        # 分步移动到终点
        steps = max(int(duration_drag / 0.02), 5)
        for i in range(1, steps + 1):
            t = i / steps
            cx = int(start.x + (end.x - start.x) * t)
            cy = int(start.y + (end.y - start.y) * t)
            pyautogui.moveTo(cx, cy)
            time.sleep(duration_drag / steps)
        # 松开之前先定住鼠标以消除滑动惯性
        time.sleep(release_wait)
    finally:
        (button_up or pyautogui.mouseUp)()


def get_current_mouse_pos() -> Point:
    """获取鼠标当前坐标。"""
    pos = pyautogui.position()
    return Point(pos.x, pos.y)
