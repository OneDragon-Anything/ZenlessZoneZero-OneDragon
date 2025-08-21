import ctypes
from typing import Optional

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.controller.pc_game_window import PcGameWindow
from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.log_utils import log


class PrintWindowScreencapper(ScreencapperBase):
    """
    使用 PrintWindow API 进行截图的策略
    """

    def __init__(self, game_win: PcGameWindow, standard_width: int, standard_height: int):
        ScreencapperBase.__init__(self, game_win, standard_width, standard_height)
        self.hwndDC: Optional[int] = None
        self.mfcDC: Optional[int] = None
        self.saveBitMap: Optional[int] = None
        self.buffer: Optional[ctypes.Array] = None
        self.bmpinfo_buffer: Optional[ctypes.Array] = None
        self.width: int = 0
        self.height: int = 0
        self.hwnd_for_dc: Optional[int] = None  # 保存获取DC时的句柄，用于正确释放DC

    def init(self) -> bool:
        """初始化Print Window截图方法，预加载资源"""
        self.cleanup()

        try:
            hwnd = self.game_win.get_hwnd()
            if not hwnd:
                raise Exception('未找到目标窗口，无法初始化Print Window')

            hwndDC = ctypes.windll.user32.GetWindowDC(hwnd)
            if not hwndDC:
                raise Exception('无法获取窗口设备上下文')

            mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
                raise Exception('无法创建兼容设备上下文')

            self.hwndDC = hwndDC
            self.mfcDC = mfcDC
            self.hwnd_for_dc = hwnd
            return True
        except Exception:
            self.cleanup()
            return False

    def capture(self, rect: Rect, independent: bool = False) -> Optional[MatLike]:
        """
        Print Window 获取窗口截图
        :param rect: 截图区域
        :param independent: 是否独立截图
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

        if self.hwndDC is None or self.mfcDC is None:
            if not self.init():
                return None

        screenshot = self._capture_with_retry(hwnd, width, height)
        if screenshot is not None:
            return screenshot

        if not self.init():
            return None

        return self._capture_with_retry(hwnd, width, height)

    def cleanup(self):
        """
        清理Print Window相关资源
        """
        if self.hwndDC or self.mfcDC or self.saveBitMap:
            try:
                if self.saveBitMap:
                    ctypes.windll.gdi32.DeleteObject(self.saveBitMap)
                if self.mfcDC:
                    ctypes.windll.gdi32.DeleteDC(self.mfcDC)
                if self.hwndDC and self.hwnd_for_dc:
                    ctypes.windll.user32.ReleaseDC(self.hwnd_for_dc, self.hwndDC)
            finally:
                self.hwndDC = None
                self.mfcDC = None
                self.saveBitMap = None
                self.buffer = None
                self.bmpinfo_buffer = None
                self.width = 0
                self.height = 0
                self.hwnd_for_dc = None

    def _capture_with_retry(self, hwnd, width, height) -> Optional[MatLike]:
        """
        尝试执行一次截图操作
        """
        try:
            if (self.saveBitMap is None
                    or self.width != width
                    or self.height != height):
                if self.saveBitMap:
                    ctypes.windll.gdi32.DeleteObject(self.saveBitMap)

                saveBitMap, buffer, bmpinfo_buffer = self._create_bitmap_resources(width, height)

                self.saveBitMap = saveBitMap
                self.buffer = buffer
                self.bmpinfo_buffer = bmpinfo_buffer
                self.width = width
                self.height = height

            return self._capture_window_to_bitmap(hwnd, width, height,
                                                  self.hwndDC, self.mfcDC, self.saveBitMap,
                                                  self.buffer, self.bmpinfo_buffer)
        except Exception:
            return None

    def _capture_independent(self, hwnd, width, height) -> Optional[MatLike]:
        """
        独立模式Print Window截图，自管理资源
        """
        hwndDC = None
        mfcDC = None
        saveBitMap = None

        try:
            hwndDC = ctypes.windll.user32.GetWindowDC(hwnd)
            if not hwndDC:
                raise Exception('无法获取窗口设备上下文')

            mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                raise Exception('无法创建兼容设备上下文')

            saveBitMap, buffer, bmpinfo_buffer = self._create_bitmap_resources(width, height, hwndDC)

            return self._capture_window_to_bitmap(hwnd, width, height, hwndDC, mfcDC,
                                                  saveBitMap, buffer, bmpinfo_buffer)
        except Exception:
            return None
        finally:
            if saveBitMap:
                ctypes.windll.gdi32.DeleteObject(saveBitMap)
            if mfcDC:
                ctypes.windll.gdi32.DeleteDC(mfcDC)
            if hwndDC:
                ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)

    def _create_bitmap_resources(self, width, height, dc_handle=None):
        """
        创建位图相关资源
        """
        if dc_handle is None:
            dc_handle = self.hwndDC

        saveBitMap = ctypes.windll.gdi32.CreateCompatibleBitmap(dc_handle, width, height)
        if not saveBitMap:
            raise Exception('无法创建兼容位图')

        buffer_size = width * height * 4
        buffer = ctypes.create_string_buffer(buffer_size)

        bmpinfo_buffer = self._create_bmpinfo_buffer(width, height)

        return saveBitMap, buffer, bmpinfo_buffer

    def _create_bmpinfo_buffer(self, width, height):
        """
        创建位图信息结构
        """
        bmpinfo_buffer = ctypes.create_string_buffer(40)
        ctypes.c_uint32.from_address(ctypes.addressof(bmpinfo_buffer)).value = 40
        ctypes.c_int32.from_address(ctypes.addressof(bmpinfo_buffer) + 4).value = width
        ctypes.c_int32.from_address(ctypes.addressof(bmpinfo_buffer) + 8).value = -height
        ctypes.c_uint16.from_address(ctypes.addressof(bmpinfo_buffer) + 12).value = 1
        ctypes.c_uint16.from_address(ctypes.addressof(bmpinfo_buffer) + 14).value = 32
        ctypes.c_uint32.from_address(ctypes.addressof(bmpinfo_buffer) + 16).value = 0
        return bmpinfo_buffer

    def _capture_window_to_bitmap(self, hwnd, width, height,
                                  hwndDC, mfcDC, saveBitMap,
                                  buffer, bmpinfo_buffer) -> Optional[MatLike]:
        """
        执行窗口截图的核心逻辑
        """
        ctypes.windll.gdi32.SelectObject(mfcDC, saveBitMap)

        result = ctypes.windll.user32.PrintWindow(hwnd, mfcDC, 0x00000002)  # PW_CLIENTONLY
        if not result:
            ctypes.windll.gdi32.BitBlt(mfcDC, 0, 0, width, height,
                                       hwndDC, 0, 0, 0x00CC0020)  # SRCCOPY

        lines = ctypes.windll.gdi32.GetDIBits(hwndDC, saveBitMap,
                                              0, height, buffer,
                                              bmpinfo_buffer, 0)  # DIB_RGB_COLORS

        if lines != height:
            return None

        img_array = np.frombuffer(buffer, dtype=np.uint8).reshape((height, width, 4))
        screenshot = cv2.cvtColor(img_array, cv2.COLOR_BGRA2RGB)

        if self.game_win.is_win_scale:
            screenshot = cv2.resize(screenshot, (self.standard_width, self.standard_height))

        return screenshot
