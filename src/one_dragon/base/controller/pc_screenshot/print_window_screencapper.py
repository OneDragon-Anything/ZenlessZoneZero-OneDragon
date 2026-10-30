import ctypes

from cv2.typing import MatLike

from one_dragon.base.controller.pc_screenshot.gdi_screencapper_base import (
    GdiCaptureContext,
    GdiScreencapperBase,
)
from one_dragon.base.geometry.rectangle import Rect

# WinAPI / GDI constants
PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002
PW_FLAGS = PW_CLIENTONLY | PW_RENDERFULLCONTENT


class PrintWindowScreencapper(GdiScreencapperBase):
    """使用 PrintWindow API 进行截图的策略"""

    def capture(self, rect: Rect, independent: bool = False) -> MatLike | None:
        """获取窗口截图

        Args:
            rect: 截图区域
            independent: 是否独立截图

        Returns:
            截图数组，失败返回 None
        """
        hwnd = self.game_win.get_hwnd()
        if not hwnd:
            return None

        width = rect.width
        height = rect.height

        if width <= 0 or height <= 0:
            return None

        if independent:
            return self._capture_independent(hwnd, width, height)

        return self._capture_shared(hwnd, width, height)

    def _do_capture(self, context: GdiCaptureContext) -> bool:
        """使用 PrintWindow API 执行截图

        Args:
            context: 截图上下文

        Returns:
            是否截图成功
        """
        return ctypes.windll.user32.PrintWindow(context.hwnd, context.mfcDC, PW_FLAGS)
