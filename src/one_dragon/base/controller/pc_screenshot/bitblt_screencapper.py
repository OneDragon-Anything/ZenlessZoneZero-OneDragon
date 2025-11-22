import ctypes

import cv2
from cv2.typing import MatLike

from one_dragon.base.controller.pc_screenshot.gdi_screencapper_base import (
    GdiScreencapperBase,
)
from one_dragon.base.geometry.rectangle import Rect

# WinAPI / GDI constants
SRCCOPY = 0x00CC0020

class BitBltScreencapper(GdiScreencapperBase):
    """使用 BitBlt API 先截取全屏再裁剪到窗口区域的策略"""

    @staticmethod
    def _get_virtual_screen_info() -> tuple[int, int, int, int]:
        """获取虚拟屏幕信息

        Returns:
            (left, top, width, height) 虚拟屏幕的位置和尺寸
        """
        left = ctypes.windll.user32.GetSystemMetrics(76)    # SM_XVIRTUALSCREEN
        top = ctypes.windll.user32.GetSystemMetrics(77)     # SM_YVIRTUALSCREEN
        width = ctypes.windll.user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
        height = ctypes.windll.user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        return left, top, width, height

    def capture(self, rect: Rect, independent: bool = False) -> MatLike | None:
        """获取全屏截图并裁剪到窗口区域

        Args:
            rect: 截图区域（窗口在屏幕上的坐标）
            independent: 是否独立截图

        Returns:
            截图数组，失败返回 None
        """
        v_left, v_top, v_width, v_height = self._get_virtual_screen_info()

        if independent:
            screenshot = self._capture_independent(0, v_width, v_height)
        else:
            screenshot = self._capture_shared(0, v_width, v_height)

        if screenshot is None:
            return None

        # 裁剪到窗口区域
        return self._crop_to_window(screenshot, rect, v_left, v_top, v_width, v_height)

    def _do_capture(self, hwnd, width, height, hwndDC, mfcDC) -> bool:
        """使用 BitBlt API 执行截图，自动处理 CAPTUREBLT 标志

        Args:
            hwnd: 窗口句柄
            width: 截图宽度
            height: 截图高度
            hwndDC: 设备上下文
            mfcDC: 内存设备上下文

        Returns:
            是否截图成功
        """
        return ctypes.windll.gdi32.BitBlt(
            mfcDC, 0, 0, width, height,
            hwndDC, 0, 0, SRCCOPY
        )

    def _crop_to_window(self, fullscreen: MatLike, rect: Rect,
                        virtual_left: int, virtual_top: int,
                        virtual_width: int, virtual_height: int) -> MatLike | None:
        """将全屏截图裁剪到窗口区域

        Args:
            fullscreen: 全屏截图
            rect: 窗口区域（屏幕绝对坐标）
            virtual_left: 虚拟屏幕左上角 X 坐标（可能为负）
            virtual_top: 虚拟屏幕左上角 Y 坐标（可能为负）
            virtual_width: 虚拟屏幕总宽度
            virtual_height: 虚拟屏幕总高度

        Returns:
            裁剪后的截图，失败返回 None
        """
        # 将窗口的绝对坐标转换为虚拟屏幕图像中的相对坐标
        x1 = max(0, min(rect.x1 - virtual_left, virtual_width))
        y1 = max(0, min(rect.y1 - virtual_top, virtual_height))
        x2 = max(0, min(rect.x2 - virtual_left, virtual_width))
        y2 = max(0, min(rect.y2 - virtual_top, virtual_height))

        if x2 <= x1 or y2 <= y1:
            return None

        screenshot = fullscreen[y1:y2, x1:x2]

        if self.game_win.is_win_scale:
            screenshot = cv2.resize(screenshot, (self.standard_width, self.standard_height))

        return screenshot
