import time

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point


class ScreenshotWithTime:

    def __init__(self, screenshot: MatLike, create_time: float):
        self.image: MatLike = screenshot
        self.create_time: float = create_time


class ControllerBase:

    def __init__(self,
                 screenshot_alive_seconds: float = 5,
                 max_screenshot_cnt: int = 0):
        """
        基础控制器的定义
        """
        self.screenshot_history: list[ScreenshotWithTime] = []
        self.screenshot_alive_seconds: float = screenshot_alive_seconds  # 截图在内存的存活时间
        self.max_screenshot_cnt: int = max_screenshot_cnt  # 内存中最多保持的截图数量

    def init_before_context_run(self) -> bool:
        """
        运行前初始化
        :return:
        """
        return False

    def cleanup_after_app_shutdown(self) -> None:
        """
        清理资源
        """
        pass

    @property
    def is_game_window_ready(self) -> bool:
        """
        游戏窗口是否已经准备好了
        :return:
        """
        return False

    def click(self, pos: Point = None, press_time: float = 0, pc_alt: bool = False) -> bool:
        """
        点击位置
        :param pos: 点击位置 (x,y) 默认分辨率下的游戏窗口里的坐标
        :param press_time: 大于0时长按若干秒
        :param pc_alt: 只在PC端有用 使用ALT键进行点击
        :return: 不在窗口区域时不点击 返回False
        """
        pass

    def screenshot(self, independent: bool = False) -> tuple[float, MatLike | None]:
        """
        截图并保存在内存中
        """
        self.before_screenshot()
        screenshot_time = time.time()
        screen = self.get_screenshot(independent)
        if screen is None:
            return screenshot_time, None
        fix_screen = self.fill_uid_black(screen)

        if self.max_screenshot_cnt > 0:
            self.screenshot_history.append(ScreenshotWithTime(fix_screen, screenshot_time))
            while len(self.screenshot_history) > self.max_screenshot_cnt:
                self.screenshot_history.pop(0)

            while (len(self.screenshot_history) > 0
                and screenshot_time - self.screenshot_history[0].create_time > self.screenshot_alive_seconds):
                self.screenshot_history.pop(0)

        return screenshot_time, fix_screen

    def before_screenshot(self) -> None:
        """
        截图前的操作 由子类实现
        """
        pass

    def get_screenshot(self, independent: bool = False) -> MatLike:
        """
        截图 如果分辨率和默认不一样则进行缩放
        由子类实现 做具体的截图
        :return: 缩放到默认分辨率的截图
        """
        pass

    def fill_uid_black(self, screen: MatLike) -> MatLike:
        """
        遮挡UID 由子类实现
        """
        return screen

    def scroll(self, down: int, pos: Point = None):
        """
        向下滚动
        :param down: 负数时为相上滚动
        :param pos: 滚动位置 默认分辨率下的游戏窗口里的坐标
        :return:
        """
        pass

    def drag_to(self, end: Point, start: Point = None, duration: float = 0.5):
        """
        按住拖拽
        :param end: 拖拽目的点
        :param start: 拖拽开始点
        :param duration: 拖拽持续时间
        :return:
        """
        pass

    def close_game(self):
        """
        关闭游戏
        :return:
        """
        pass

    def input_str(self, to_input: str, interval: float = 0.1):
        """
        输入文本 需要自己先选择好输入框
        :param to_input: 文本
        :param interval: 输入间隙 秒
        :return:
        """
        pass

    def delete_all_input(self):
        """
        删除所有输入文本
        :return:
        """
        pass
