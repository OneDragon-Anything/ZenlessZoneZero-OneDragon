import ctypes

from one_dragon.base.controller.pc_screenshot.gdi_screencapper_base import GdiScreencapperBase

# WinAPI / GDI constants
PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002
PW_FLAGS = PW_CLIENTONLY | PW_RENDERFULLCONTENT


class PrintWindowScreencapper(GdiScreencapperBase):
    """使用 PrintWindow API 进行截图的策略"""

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
        result = ctypes.windll.user32.PrintWindow(hwnd, mfcDC, PW_FLAGS)
        if not result:
            return False
        return True
