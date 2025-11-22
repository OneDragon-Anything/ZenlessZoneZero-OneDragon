import ctypes

from cv2.typing import MatLike

from one_dragon.base.controller.pc_screenshot.gdi_screencapper_base import (
    GdiScreencapperBase,
)
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log

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

        # 使用实例级锁保护对共享 GDI 资源的使用
        with self._lock:
            # 确保 mfcDC 已初始化
            if self.mfcDC is None and not self.init():
                return None

            # 每次临时获取窗口 DC
            hwndDC = ctypes.windll.user32.GetDC(hwnd)
            if not hwndDC:
                return None

            try:
                return self._capture_with_retry(hwnd, width, height, hwndDC)
            finally:
                # 始终释放窗口 DC
                try:
                    ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
                except Exception:
                    log.debug("ReleaseDC 失败", exc_info=True)

    def _do_capture(self, hwnd, width, height, hwndDC, mfcDC) -> bool:
        """使用 PrintWindow API 执行截图

        Args:
            hwnd: 窗口句柄
            width: 截图宽度
            height: 截图高度
            hwndDC: 设备上下文
            mfcDC: 内存设备上下文

        Returns:
            是否截图成功
        """
        return ctypes.windll.user32.PrintWindow(hwnd, mfcDC, PW_FLAGS)
