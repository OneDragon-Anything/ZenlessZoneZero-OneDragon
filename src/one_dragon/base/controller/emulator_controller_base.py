import cv2

from cv2.typing import MatLike
from one_dragon.module.device.device import Device
from one_dragon.module.config.config import AzurLaneConfig
from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.geometry.point import Point
class EmulatorControllerBase(ControllerBase):

    def __init__(self, win_title: str,instance_idx,
                 standard_width: int = 1920,
                 standard_height: int = 1080):
        ControllerBase.__init__(self)
        self.standard_width: int = standard_width
        self.standard_height: int = standard_height
        self.emulator_width: int
        self.emulator_height: int
        config = AzurLaneConfig(config_name='alas',instance_idx=instance_idx)
        self.device = Device(config=config)

        self.sct = None

    def init_before_context_run(self) -> bool:
        return True
    
    def is_game_window_ready(self) -> bool:
        """
        游戏窗口是否已经准备好了
        :return:
        """
        return self.device.app_is_running()
    
    def get_screenshot(self, independent: bool = False) -> MatLike:
        """
        截图 如果分辨率和默认不一样则进行缩放
        :return: 截图
        """
        screenshot = cv2.cvtColor(self.device.screenshot(), cv2.COLOR_BGRA2RGB)


        self.emulator_width = screenshot.shape[1]
        self.emulator_height = screenshot.shape[0]

        if self.emulator_width != self.standard_width and self.emulator_height != self.standard_height:
            result = cv2.resize(screenshot, (self.standard_width, self.standard_height),interpolation=cv2.INTER_AREA)
        else:
            result = screenshot
        return result

    def convert_coordinate(self, point: Point) -> Point:
        """
        根据模拟器的截图分辨率进行坐标转换
        :param point: 待转换的坐标
        :return: 转换后的坐标
        """
        point.x = self.emulator_width/self.standard_width*point.x
        point.y = self.emulator_height/self.standard_height*point.y
        return point

    def click(self, pos: Point = None, press_time: float = 0, pc_alt: bool = False) -> bool:
        """
        点击位置
        :param pos: 游戏中的位置 (x,y)
        :param press_time: 大于0时长按若干秒
        :param pc_alt: 只在PC端有用 使用ALT键进行点击
        :return: 不在窗口区域时不点击 返回False
        """
        pos=self.convert_coordinate(pos)
        if press_time is not None and press_time > 0:
            self.device.long_clickxy(pos, press_time)
        else:
            self.device.clickxy(pos)
        return True

    def drag_to(self, end: Point, start: Point = None, duration: float = 0.5):
        """
        按住拖拽
        :param end: 拖拽目的点
        :param start: 拖拽开始点
        :param duration: 拖拽持续时间
        :return:
        """
        from_pos: Point
        end=self.convert_coordinate(end)
        start=self.convert_coordinate(start)
        self.device.drag(start, end, swipe_duration= duration,point_random=(0, 0, 0, 0),shake_random=(0, 0, 0, 0))

    def active_window(self) -> None:
        """
        前置窗口
        """
        self.device.emulator_start()



