import ctypes
from typing import Optional
import threading
from cv2.typing import MatLike
from one_dragon.base.controller.pc_screenshot.screencapper_base import ScreencapperBase
import numpy as np
import cv2
from cv2.typing import MatLike

# 常量
DIB_RGB_COLORS = 0
BI_RGB = 0
SRCCOPY = 0x00CC0020


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", ctypes.c_uint32 * 3),
    ]

class BitmapResourceMixin:
    """
    Mixin 提供位图资源创建与缓冲区转换工具。
    设计要点与实现来源于 src/.../bitmap_resources.py
    """
    def _create_bmpinfo_buffer(self, width: int, height: int) -> BITMAPINFO:
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = int(width)
        bmi.bmiHeader.biHeight = -int(height)  # top-down DIB
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bmi.bmiHeader.biSizeImage = 0
        bmi.bmiHeader.biXPelsPerMeter = 0
        bmi.bmiHeader.biYPelsPerMeter = 0
        bmi.bmiHeader.biClrUsed = 0
        bmi.bmiHeader.biClrImportant = 0
        return bmi

    def _create_bitmap_resources(self, width: int, height: int, hwndDC: Optional[int] = None):
        bmi = self._create_bmpinfo_buffer(width, height)
        ppvBits = ctypes.c_void_p()
        hdc_val = int(hwndDC) if hwndDC else 0
        hBitmap = ctypes.windll.gdi32.CreateDIBSection(
            hdc_val,
            ctypes.byref(bmi),
            DIB_RGB_COLORS,
            ctypes.byref(ppvBits),
            None,
            0
        )
        if not hBitmap:
            raise Exception("CreateDIBSection 失败")
        if not ppvBits.value:
            try:
                ctypes.windll.gdi32.DeleteObject(hBitmap)
            except Exception:
                pass
            raise Exception("CreateDIBSection 未返回像素指针")
        size = int(width) * int(height) * 4
        buffer = (ctypes.c_ubyte * size).from_address(ppvBits.value)
        return hBitmap, buffer, bmi

    def _release_bitmap_resources(self, saveBitMap: Optional[int], mfcDC: Optional[int] = None) -> None:
        try:
            if saveBitMap:
                ctypes.windll.gdi32.DeleteObject(int(saveBitMap))
        except Exception:
            pass
        try:
            if mfcDC:
                ctypes.windll.gdi32.DeleteDC(int(mfcDC))
        except Exception:
            pass

    def buffer_to_ndarray(self, buffer: ctypes.Array, width: int, height: int) -> np.ndarray:
        size = int(width) * int(height) * 4
        arr = np.ctypeslib.as_array(buffer)
        if arr.size != size:
            raise ValueError("buffer 大小与宽高不匹配")
        img = arr.reshape((height, width, 4))
        return img

    def _capture_bitmap_to_image(
        self,
        hwnd: int,
        width: int,
        height: int,
        hwndDC: int,
        mfcDC: int,
        saveBitMap: int,
        buffer: ctypes.Array,
        bmpinfo_buffer: BITMAPINFO,
        *,
        use_printwindow: bool = True,
        pw_flags: int = 0x00000003,
        is_win_scale: bool = False,
        standard_width: int = 0,
        standard_height: int = 0
    ) -> Optional[MatLike]:
        if not all([hwndDC, mfcDC, saveBitMap, buffer, bmpinfo_buffer]):
            return None
        prev_obj = None
        try:
            prev_obj = ctypes.windll.gdi32.SelectObject(int(mfcDC), int(saveBitMap))
            if use_printwindow:
                result = ctypes.windll.user32.PrintWindow(int(hwnd), int(mfcDC), int(pw_flags))
                if not result:
                    return None
            else:
                res = ctypes.windll.gdi32.BitBlt(int(mfcDC), 0, 0, int(width), int(height), int(hwndDC), 0, 0, SRCCOPY)
                if not res:
                    return None
            lines = ctypes.windll.gdi32.GetDIBits(
                int(mfcDC),
                int(saveBitMap),
                0,
                int(height),
                ctypes.cast(buffer, ctypes.c_void_p),
                ctypes.byref(bmpinfo_buffer),
                DIB_RGB_COLORS
            )
            if lines != int(height):
                return None
            img_array = self.buffer_to_ndarray(buffer, width, height)
            screenshot = cv2.cvtColor(img_array, cv2.COLOR_BGRA2RGB)
            if is_win_scale and standard_width and standard_height:
                screenshot = cv2.resize(screenshot, (standard_width, standard_height))
            return screenshot
        except Exception:
            return None
        finally:
            try:
                if prev_obj is not None:
                    ctypes.windll.gdi32.SelectObject(int(mfcDC), int(prev_obj))
            except Exception:
                pass

from one_dragon.utils.log_utils import log
from one_dragon.base.geometry.rectangle import Rect

class GdiScreencapperBase(ScreencapperBase, BitmapResourceMixin):
    def __init__(self, game_win, standard_width, standard_height):
        ScreencapperBase.__init__(self, game_win, standard_width, standard_height)
        self.hwndDC: Optional[int] = None
        self.mfcDC: Optional[int] = None
        self.saveBitMap: Optional[int] = None
        self.buffer: Optional[ctypes.Array] = None
        self.bmpinfo_buffer: Optional[ctypes.Array] = None
        self.width: int = 0
        self.height: int = 0
        self.hwnd_for_dc: Optional[int] = None
        self._lock = threading.RLock()
        self._init_name = getattr(self, "_init_name", "GDI")

    def init(self) -> bool:
        self.cleanup()
        try:
            hwnd = self.game_win.get_hwnd()
            if not hwnd:
                raise Exception(f'未找到目标窗口，无法初始化{self._init_name}')
            hwndDC = ctypes.windll.user32.GetDC(hwnd)
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
        except Exception as e:
            log.exception("初始化 %s 失败: %s", self._init_name, e)
            self.cleanup()
            return False

    def ensure_bitmap_resources(self, width, height, hwndDC_for_create=None):
        needs_create = (self.saveBitMap is None or self.width != width or self.height != height)
        if needs_create:
            with self._lock:
                if (self.saveBitMap is None or self.width != width or self.height != height):
                    if self.saveBitMap:
                        if self.mfcDC and getattr(self, "_selected_prev", None) is not None:
                            try:
                                ctypes.windll.gdi32.SelectObject(self.mfcDC, self._selected_prev)
                            except Exception:
                                log.exception("替换位图前恢复原始对象失败")
                            finally:
                                self._selected_prev = None
                        try:
                            ctypes.windll.gdi32.DeleteObject(self.saveBitMap)
                        except Exception:
                            log.exception("删除旧 saveBitMap 失败")
                    try:
                        saveBitMap, buffer, bmpinfo_buffer = self._create_bitmap_resources(width, height, hwndDC_for_create)
                    except Exception as e:
                        log.exception("创建位图资源失败: %s", e)
                        return None
                    self.saveBitMap = saveBitMap
                    self.buffer = buffer
                    self.bmpinfo_buffer = bmpinfo_buffer
                    self.width = width
                    self.height = height
        return True

    def _try_capture_once(self, hwnd, width, height, use_printwindow=False, pw_flags=None):
        if self.saveBitMap is None or self.width != width or self.height != height:
            res = self.ensure_bitmap_resources(width, height)
            if res is None:
                return None
        return self._capture_bitmap_to_image(
            hwnd=hwnd,
            width=width,
            height=height,
            hwndDC=self.hwndDC,
            mfcDC=self.mfcDC,
            saveBitMap=self.saveBitMap,
            buffer=self.buffer,
            bmpinfo_buffer=self.bmpinfo_buffer,
            use_printwindow=use_printwindow,
            pw_flags=pw_flags,
            is_win_scale=getattr(self.game_win, "is_win_scale", False),
            standard_width=self.standard_width,
            standard_height=self.standard_height
        )

    def capture_common(self, rect: Rect, independent: bool, use_printwindow=False, pw_flags=None, retry=False) -> Optional[MatLike]:
        hwnd = self.game_win.get_hwnd()
        if not hwnd:
            return None
        width = rect.width
        height = rect.height
        if width <= 0 or height <= 0:
            return None
        if independent:
            return self._capture_independent_generic(hwnd, width, height, use_printwindow, pw_flags)
        with self._lock:
            if self.hwndDC is None or self.mfcDC is None:
                if not self.init():
                    return None
            screenshot = self._try_capture_once(hwnd, width, height, use_printwindow, pw_flags)
            if screenshot is not None:
                return screenshot
            if retry:
                if not self.init():
                    return None
                return self._try_capture_once(hwnd, width, height, use_printwindow, pw_flags)
            return None

    def _capture_independent_generic(self, hwnd, width, height, use_printwindow=False, pw_flags=None):
        hwndDC = None
        mfcDC = None
        saveBitMap = None
        try:
            hwndDC = ctypes.windll.user32.GetDC(hwnd)
            if not hwndDC:
                raise Exception('无法获取窗口设备上下文')
            mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                raise Exception('无法创建兼容设备上下文')
            saveBitMap, buffer, bmpinfo_buffer = self._create_bitmap_resources(width, height, hwndDC)
            return self._capture_bitmap_to_image(
                hwnd=hwnd,
                width=width,
                height=height,
                hwndDC=hwndDC,
                mfcDC=mfcDC,
                saveBitMap=saveBitMap,
                buffer=buffer,
                bmpinfo_buffer=bmpinfo_buffer,
                use_printwindow=use_printwindow,
                pw_flags=pw_flags,
                is_win_scale=getattr(self.game_win, "is_win_scale", False),
                standard_width=self.standard_width,
                standard_height=self.standard_height
            )
        except Exception as e:
            log.exception("独立模式截图失败: %s", e)
            return None
        finally:
            try:
                if saveBitMap:
                    ctypes.windll.gdi32.DeleteObject(saveBitMap)
                if mfcDC:
                    ctypes.windll.gdi32.DeleteDC(mfcDC)
                if hwndDC:
                    ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
            except Exception:
                log.exception("独立模式资源释放失败")

    def cleanup(self):
        with self._lock:
            if not (self.hwndDC or self.mfcDC or self.saveBitMap):
                self.hwndDC = None
                self.mfcDC = None
                self.saveBitMap = None
                self.buffer = None
                self.bmpinfo_buffer = None
                self.width = 0
                self.height = 0
                self.hwnd_for_dc = None
                return
            if self.saveBitMap:
                if self.mfcDC and getattr(self, "_selected_prev", None) is not None:
                    try:
                        ctypes.windll.gdi32.SelectObject(self.mfcDC, self._selected_prev)
                    except Exception:
                        log.exception("cleanup: 恢复原始对象失败")
                    finally:
                        self._selected_prev = None
                try:
                    ctypes.windll.gdi32.DeleteObject(self.saveBitMap)
                except Exception:
                    log.exception("删除 saveBitMap 失败")
            if self.mfcDC:
                try:
                    ctypes.windll.gdi32.DeleteDC(self.mfcDC)
                except Exception:
                    log.exception("删除 mfcDC 失败")
            if self.hwndDC and self.hwnd_for_dc:
                try:
                    ctypes.windll.user32.ReleaseDC(self.hwnd_for_dc, self.hwndDC)
                except Exception:
                    log.exception("ReleaseDC 失败")
            self.hwndDC = None
            self.mfcDC = None
            self.saveBitMap = None
            self.buffer = None
            self.bmpinfo_buffer = None
            self.width = 0
            self.height = 0
            self.hwnd_for_dc = None
