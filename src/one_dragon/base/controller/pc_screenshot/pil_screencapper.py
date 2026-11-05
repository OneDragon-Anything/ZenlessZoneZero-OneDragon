import sys
from io import BytesIO

import numpy as np
from cv2.typing import MatLike
from pyautogui import screenshot as pyautogui_screenshot

from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect

if sys.platform == 'darwin':
    import Quartz
    from AppKit import NSBitmapImageRep, NSPNGFileType
    from PIL import Image


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
        """按窗口 ID 截取游戏画面，避免桌面上的其他窗口遮挡。"""
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

        bitmap = NSBitmapImageRep.alloc().initWithCGImage_(image_ref)
        png_data = bitmap.representationUsingType_properties_(NSPNGFileType, {})
        if png_data is None:
            return None

        image = Image.open(BytesIO(bytes(png_data.bytes()))).convert('RGB')
        screenshot = np.asarray(image)
        game_height = round(
            screenshot.shape[1] * self.standard_height / self.standard_width
        )
        if screenshot.shape[0] > game_height:
            screenshot = screenshot[-game_height:, :, :]
        return screenshot

    def cleanup(self):
        """PIL不需要清理资源"""
        pass
