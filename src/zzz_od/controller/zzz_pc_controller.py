import ctypes
import time

from cv2.typing import MatLike

from one_dragon.base.controller.pc_controller_base import PcControllerBase
from one_dragon.utils import cv2_utils
from zzz_od.config.game_config import GameConfig
from zzz_od.const import game_const
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum


class ZPcController(PcControllerBase):

    def __init__(
            self,
            game_config: GameConfig,
            screenshot_method: str,
            standard_width: int = 1920,
            standard_height: int = 1080
    ):
        PcControllerBase.__init__(self,
                                  screenshot_method=screenshot_method,
                                  standard_width=standard_width,
                                  standard_height=standard_height)

        self.game_config: GameConfig = game_config
        self.action_keys = self.game_config.get_action_keys('keyboard')
        self.gamepad_action_keys = self.game_config.get_gamepad_action_keys()
        self.mouse_flash_duration: float = game_config.mouse_flash_duration

        self.is_moving: bool = False  # 是否正在移动
        self.turn_dx: float = game_config.turn_dx
        self.gamepad_turn_speed: float = game_config.gamepad_turn_speed

    def init_before_context_run(self) -> bool:
        """运行前根据配置启用后台/前台模式，刷新快照配置"""
        if self.game_config.background_mode:
            self.enable_background_mode(self.game_config.background_gamepad_type)
        else:
            self.enable_foreground_mode()
        self.turn_dx = self.game_config.turn_dx
        self.gamepad_turn_speed = self.game_config.gamepad_turn_speed
        self.mouse_flash_duration = self.game_config.mouse_flash_duration
        return PcControllerBase.init_before_context_run(self)

    def fill_uid_black(self, screen: MatLike) -> MatLike:
        """
        遮挡UID 由子类实现
        """
        rect = ScreenNormalWorldEnum.UID.value.rect

        return cv2_utils.mark_area_as_color(
            screen,
            pos=[rect.x1, rect.y1, rect.width, rect.height],
            color=game_const.YOLO_DEFAULT_COLOR,
            new_image=True
        )

    def enable_keyboard(self):
        PcControllerBase.enable_keyboard(self)
        self.action_keys = self.game_config.get_action_keys('keyboard')

    def enable_xbox(self):
        PcControllerBase.enable_xbox(self)
        self.action_keys = self.game_config.get_action_keys('xbox')
        self.gamepad_action_keys = self.game_config.get_gamepad_action_keys('xbox')

    def enable_ds4(self):
        PcControllerBase.enable_ds4(self)
        self.action_keys = self.game_config.get_action_keys('ds4')
        self.gamepad_action_keys = self.game_config.get_gamepad_action_keys('ds4')

    def _action_btn(self, key: str, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """通用按键动作：按下/释放/点按"""
        if press:
            self.btn_press(key, press_time)
        elif release:
            self.btn_release(key)
        else:
            self.btn_tap(key)

    def dodge(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """闪避"""
        self._action_btn(self.action_keys['dodge'], press, press_time, release)

    def switch_next(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """切换角色-下一个"""
        self._action_btn(self.action_keys['switch_next'], press, press_time, release)

    def switch_prev(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """切换角色-上一个"""
        self._action_btn(self.action_keys['switch_prev'], press, press_time, release)

    def normal_attack(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """普通攻击"""
        self._action_btn(self.action_keys['normal_attack'], press, press_time, release)

    def special_attack(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """特殊攻击"""
        self._action_btn(self.action_keys['special_attack'], press, press_time, release)

    def ultimate(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """终结技"""
        self._action_btn(self.action_keys['ultimate'], press, press_time, release)

    def chain_left(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """连携技-左"""
        self._action_btn(self.action_keys['chain_left'], press, press_time, release)

    def chain_right(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """连携技-右"""
        self._action_btn(self.action_keys['chain_right'], press, press_time, release)

    def move_w(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """向前移动"""
        self._action_btn(self.action_keys['move_w'], press, press_time, release)

    def move_s(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """向后移动"""
        self._action_btn(self.action_keys['move_s'], press, press_time, release)

    def move_a(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """向左移动"""
        self._action_btn(self.action_keys['move_a'], press, press_time, release)

    def move_d(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """向右移动"""
        self._action_btn(self.action_keys['move_d'], press, press_time, release)

    def interact(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """交互"""
        self._action_btn(self.action_keys['interact'], press, press_time, release)

    def lock(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """锁定敌人"""
        self._action_btn(self.action_keys['lock'], press, press_time, release)

    def chain_cancel(self, press: bool = False, press_time: float | None = None, release: bool = False) -> None:
        """取消连携"""
        self._action_btn(self.action_keys['chain_cancel'], press, press_time, release)

    def start_moving_forward(self) -> None:
        """
        开始向前移动
        """
        if self.is_moving:
            return
        self.is_moving = True
        self.move_w(press=True)

    def stop_moving_forward(self) -> None:
        """
        停止向前移动
        """
        self.is_moving = False
        self.move_w(release=True)

    def turn_by_distance(self, d: float):
        """
        横向转向 按距离转

        Args:
            d: 正数往右转 负数往左转
        """
        self.move_mouse_relative(d, 0)

    def turn_by_angle_diff(self, angle_diff: float) -> None:
        """
        按照给定角度偏移进行转向

        Args:
            angle_diff: 角度偏移 逆时针为正

        Returns:
            None
        """
        self.turn_by_distance(self.turn_dx * angle_diff)

    def turn_vertical_by_distance(self, d: float):
        """
        纵向转向 按距离转

        Args:
            d: 正数往下转 负数往上转
        """
        self.move_mouse_relative(0, d)

    def move_mouse_relative(self, dx: float, dy: float):
        """
        相对移动鼠标

        Args:
            dx: 横向移动距离，正数向右
            dy: 纵向移动距离，正数向下
        """
        if dx == 0 and dy == 0:
            return
        if self.background_mode:
            self._gamepad_turn(dx, dy)
        else:
            self._ensure_mouse_mode()
            ctypes.windll.user32.mouse_event(0x0001, int(dx), int(dy))

    def _gamepad_turn(self, dx: float, dy: float) -> None:
        """
        手柄右摇杆模拟鼠标转向

        将鼠标像素距离换算为右摇杆满偏转持续时间。
        Y 轴取反：鼠标向下(+dy)对应摇杆向下(-y)。

        Args:
            dx: 水平像素距离，正数向右
            dy: 垂直像素距离，正数向下
        """
        if dx == 0 and dy == 0:
            return
        if self.gamepad_turn_speed <= 0:
            return

        self._ensure_gamepad_mode()

        max_d = max(abs(dx), abs(dy))
        stick_x = dx / max_d
        stick_y = -dy / max_d  # 鼠标下(+) → 摇杆下(-y)

        duration = max_d / self.gamepad_turn_speed

        pad = self.btn_controller.pad
        try:
            pad.right_joystick_float(stick_x, stick_y)
            pad.update()
            time.sleep(duration)
        finally:
            pad.right_joystick_float(0, 0)
            pad.update()
