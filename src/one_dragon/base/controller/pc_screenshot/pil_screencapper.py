from typing import Optional

import cv2
import numpy as np
from cv2.typing import MatLike
from pyautogui import screenshot as pyautogui_screenshot

from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect


class PilScreencapper(ScreencapperBase):
    """使用 PIL (pyautogui) 进行截图的策略"""

    def init(self) -> bool:
        """初始化 PIL 截图方法

        PIL 不需要初始化

        Returns:
            始终返回 True
        """
        return True

    def capture(self, rect: Rect, independent: bool = False) -> Optional[MatLike]:
        """使用 PIL 截图

        Args:
            rect: 截图区域
            independent: 是否独立截图

        Returns:
            截图数组，失败返回 None
        """
        try:
            img = pyautogui_screenshot(region=(rect.x1, rect.y1, rect.width, rect.height))
            screenshot = np.array(img)
        except Exception:
            return None

        if self.game_win.is_win_scale:
            result = cv2.resize(screenshot, (self.standard_width, self.standard_height))
        else:
            result = screenshot

        return result

    def cleanup(self):
        """PIL不需要清理资源"""
        pass
