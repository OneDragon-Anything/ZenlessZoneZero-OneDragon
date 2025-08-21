from typing import Optional

import cv2
import numpy as np
from cv2.typing import MatLike
from pyautogui import screenshot as pyautogui_screenshot

from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log


class PilScreencapper(ScreencapperBase):
    """
    使用 PIL (pyautogui) 进行截图的策略
    """

    def init(self) -> bool:
        """
        PIL不需要初始化
        """
        return True

    def capture(self, rect: Rect, independent: bool = False) -> Optional[MatLike]:
        """
        使用PIL截图
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
        """
        PIL不需要清理资源
        """
        pass
