import ctypes
from cv2.typing import MatLike
from typing import Optional

from one_dragon.base.controller.emulator_controller_base import EmulatorControllerBase
from one_dragon.utils import cv2_utils
from zzz_od.config.game_config import GameConfig
from zzz_od.const import game_const
from zzz_od.screen_area.screen_normal_world import ScreenNormalWorldEnum_Emulator

from one_dragon.base.geometry.point import Point
class ZEmulatorController(EmulatorControllerBase):

    def __init__(self, game_config: GameConfig,instance_idx,
                 win_title: str,
                 standard_width: int = 1920,
                 standard_height: int = 1080):
        EmulatorControllerBase.__init__(self,
                                  win_title=win_title,instance_idx=instance_idx,
                                  standard_width=standard_width,
                                  standard_height=standard_height)

        self.game_config: GameConfig = game_config


    def init_before_context_run(self) -> bool:
        """
        运行前初始化
        :return:
        """
        return True
 
    def fill_uid_black(self, screen: MatLike) -> MatLike:
        """
        遮挡UID
        """
        rect = ScreenNormalWorldEnum_Emulator.UID.value.rect

        return cv2_utils.mark_area_as_color(
            screen,
            pos=[rect.x1, rect.y1, rect.width, rect.height],
            color=game_const.YOLO_DEFAULT_COLOR,
            new_image=True
        )

    def dodge(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        闪避
        :return:
        """
        dodge_point = Point(1702, 890)
        if press:
            self.click(dodge_point,press_time)
        elif release:
            pass
        else:
            self.click(dodge_point)

    def switch_next(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        切换角色-下一个
        :return:
        """
        switch_next_point = Point(1700, 682)
        if press:
            self.click(pos=switch_next_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=switch_next_point)

    def switch_prev(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        切换角色-上一个
        :return:
        """
        switch_prev_point_start = Point(1680, 700)
        switch_prev_point_end = Point(1619, 637)
        if press:
            self.drag_to(start=switch_prev_point_start, end=switch_prev_point_end,duration=0.15)
        elif release:
            pass
        else:
            self.drag_to(start=switch_prev_point_start, end=switch_prev_point_end,duration=0.15)

    def normal_attack(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        普通攻击
        """
        normal_attack_point = Point(1520, 778)
        if press:
            self.click(pos=normal_attack_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=normal_attack_point)

    def special_attack(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        特殊攻击
        """
        special_attack_point = Point(1344, 900)
        if press:
            self.click(pos=special_attack_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=special_attack_point)

    def ultimate(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        终结技
        """
        ultimate_point = Point(1690, 488)
        if press:
            self.click(pos=ultimate_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=ultimate_point)

    def chain_left(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        连携技-左
        """
        chain_left_point = Point(350, 885)
        if press:
            self.click(pos=chain_left_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=chain_left_point)

    def chain_right(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        连携技-右
        """
        chain_right_point = Point(1650, 885)
        if press:
            self.click(pos=chain_right_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=chain_right_point)

    def move_w(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        向前移动
        :return:
        """
        move_w_point = Point(340, 635)
        if press:
            self.click(pos=move_w_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=move_w_point)

    def move_s(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        向后移动
        """
        move_s_point = Point(340, 893)
        if press:
            self.click(pos=move_s_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=move_s_point)

    def move_a(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        向左移动
        """
        move_a_point = Point(210, 765)
        if press:
            self.click(pos=move_a_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=move_a_point)

    def move_d(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        向右移动
        """
        move_d_point = Point(477, 761)
        if press:
            self.click(pos=move_d_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=move_d_point)

    def interact(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        交互
        """
        interact_point = Point(1520, 778)
        if press:
            self.click(pos=interact_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=interact_point)


    def turn_by_distance(self, d: float):
        """
        横向转向 按距离转
        :param d: 正数往右转 负数往左转
        :return:
        """
        ctypes.windll.user32.mouse_event(0x0001, int(d), 0)

    def lock(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        锁定敌人
        """
        lock_point = Point(1520, 778)
        if press:
            self.click(pos=lock_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=lock_point,press_time=0.2)

    def chain_cancel(self, press: bool = False, press_time: Optional[float] = None, release: bool = False) -> None:
        """
        取消连携
        """
        chain_cancel_point = Point(1100, 1014)
        if press:
            self.click(pos=chain_cancel_point,press_time=press_time)
        elif release:
            pass
        else:
            self.click(pos=chain_cancel_point)

