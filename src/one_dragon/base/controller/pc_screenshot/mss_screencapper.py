from typing import Optional

import cv2
import numpy as np
from cv2.typing import MatLike
from mss.base import MSSBase

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect


class MssScreencapper(ScreencapperBase):
    """使用 MSS 进行截图的策略"""

    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        ScreencapperBase.__init__(self, game_win, standard_width, standard_height)
        self.mss_instance: Optional[MSSBase] = None

    def init(self) -> bool:
        """初始化 MSS 截图方法

        Returns:
            是否初始化成功
        """
        self.cleanup()
        try:
            from mss import mss
            self.mss_instance = mss()
            return True
        except Exception:
            return False

    def capture(self, rect: Rect, independent: bool = False) -> Optional[MatLike]:
        """截图 如果分辨率和默认不一样则进行缩放

        Args:
            rect: 截图区域
            independent: 是否独立截图

        Returns:
            截图数组，失败返回 None
        """
        monitor = {"top": rect.y1, "left": rect.x1, "width": rect.width, "height": rect.height}

        try:
            if independent:
                from mss import mss
                with mss() as mss_instance:
                    screenshot = cv2.cvtColor(np.array(mss_instance.grab(monitor)), cv2.COLOR_BGRA2RGB)
            else:
                if self.mss_instance is None:
                    if not self.init():
                        return None
                screenshot = cv2.cvtColor(np.array(self.mss_instance.grab(monitor)), cv2.COLOR_BGRA2RGB)
        except Exception:
            if not independent:
                if self.init():  # 重新初始化
                    try:
                        screenshot = cv2.cvtColor(np.array(self.mss_instance.grab(monitor)), cv2.COLOR_BGRA2RGB)
                    except Exception:
                        return None
                else:
                    return None
            else:
                return None

        if self.game_win.is_win_scale:
            result = cv2.resize(screenshot, (self.standard_width, self.standard_height))
        else:
            result = screenshot

        return result

    def cleanup(self):
        """清理 MSS 相关资源"""
        if self.mss_instance is not None:
            try:
                self.mss_instance.close()
            finally:
                self.mss_instance = None
