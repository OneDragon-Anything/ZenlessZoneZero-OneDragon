import sys

import numpy as np
from cv2.typing import MatLike
from pyautogui import screenshot as pyautogui_screenshot

from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect

if sys.platform == 'darwin':
    import Quartz


class PilScreencapper(ScreencapperBase):
    """使用 PIL (pyautogui) 进行截图的策略"""

    def init(self) -> bool:
        """初始化 PIL 截图方法

        PIL 不需要初始化

        Returns:
            始终返回 True
        """
        return True

    def capture(self, rect: Rect, independent: bool = False) -> MatLike | None:
        """使用 PIL 截图

        Args:
            rect: 截图区域
            independent: 是否独立截图

        Returns:
            截图数组，失败返回 None
        """
        try:
            if sys.platform == 'darwin':
                return self._capture_mac_window()

            img = pyautogui_screenshot(region=(rect.x1, rect.y1, rect.width, rect.height))
            screenshot = np.array(img)
        except Exception:
            return None

        return screenshot

    def _capture_mac_window(self) -> MatLike | None:
        """按窗口 ID 截取游戏画面，转换到 sRGB 色彩空间并裁剪标题栏。"""
        window_id = self.game_win.get_hwnd()
        if window_id is None:
            return None

        image_ref = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            window_id,
            Quartz.kCGWindowImageBoundsIgnoreFraming,
        )
        if image_ref is None:
            return None

        width = int(Quartz.CGImageGetWidth(image_ref))
        height = int(Quartz.CGImageGetHeight(image_ref))
        if width <= 0 or height <= 0:
            return None

        game_height = min(
            height,
            round(width * self.standard_height / self.standard_width),
        )
        title_height = max(0, height - game_height)
        if title_height > 0:
            cropped_ref = Quartz.CGImageCreateWithImageInRect(
                image_ref,
                Quartz.CGRectMake(0, title_height, width, game_height),
            )
            if cropped_ref is not None:
                image_ref = cropped_ref
                height = game_height

        srgb_space = Quartz.CGColorSpaceCreateWithName(
            Quartz.kCGColorSpaceSRGB
        )
        buffer = bytearray(height * width * 4)
        context = Quartz.CGBitmapContextCreate(
            buffer,
            width,
            height,
            8,
            width * 4,
            srgb_space,
            Quartz.kCGImageAlphaPremultipliedLast
            | Quartz.kCGBitmapByteOrder32Big,
        )
        if context is None:
            return None

        Quartz.CGContextDrawImage(
            context,
            Quartz.CGRectMake(0, 0, width, height),
            image_ref,
        )
        screenshot = np.frombuffer(buffer, dtype=np.uint8).reshape(
            (height, width, 4)
        )[:, :, :3].copy()
        return screenshot

    def cleanup(self):
        """PIL不需要清理资源"""
        pass
